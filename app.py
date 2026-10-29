"""
Accessible Banking Companion — complete web prototype
INNOVEX | Dexathon 2026

IMPORTANT:
This is an educational demonstration, not a real banking service.
Balances and transactions are sample data. Bank linking, biometric options,
alerts, and payments are simulated. Never enter real banking credentials.
"""
from __future__ import annotations

import hmac
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template, request,
    session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("BANKING_DB_PATH", APP_DIR / "banking_companion.db"))
SESSION_TIMEOUT_MINUTES = 10
MAX_LOGIN_ATTEMPTS = 3
LOCK_MINUTES = 15
DEMO_BALANCE = 48250.75
LANGUAGES = {"English": "en-IN", "தமிழ் (Tamil)": "ta-IN", "हिन्दी (Hindi)": "hi-IN"}
ACCESS_OPTIONS = [
    "Visual impairment or blindness", "Hearing impairment", "Mobility impairment",
    "Cognitive or learning difficulties", "Elderly user needing additional assistance",
    "Other accessibility needs", "Prefer not to disclose",
]
BANKS = [
    "State Bank of India", "Indian Bank", "Canara Bank", "HDFC Bank", "ICICI Bank",
    "Axis Bank", "Bank of Baroda", "Union Bank of India",
]
SECURITY_QUESTIONS = [
    "What is your favorite teacher's name?",
    "What was the name of your first school?",
    "What is your favorite city?",
]
SAMPLE_TRANSACTIONS = [
    {"date": "2026-10-27", "description": "Electricity Bill (TNEB)", "type": "Debit", "amount": 1450.00},
    {"date": "2026-10-26", "description": "Pension Credit", "type": "Credit", "amount": 18500.00},
    {"date": "2026-10-24", "description": "Grocery Store", "type": "Debit", "amount": 2310.50},
    {"date": "2026-10-22", "description": "Pharmacy", "type": "Debit", "amount": 865.25},
    {"date": "2026-10-20", "description": "Mobile Recharge", "type": "Debit", "amount": 299.00},
]
FRAUD_TOPICS = [
    {
        "title": "OTP scams",
        "description": "Scammers pretend to be bank staff and ask for a one-time password.",
        "do": ["Hang up and contact your bank using an official number.", "Treat every OTP as secret."],
        "dont": ["Never read an OTP to anyone.", "Never click unexpected links."],
    },
    {
        "title": "UPI scams",
        "description": "A fraudster may send a collect request and claim you will receive money.",
        "do": ["Enter your UPI PIN only to make a payment.", "Check the recipient before approving."],
        "dont": ["Do not approve unknown collect requests.", "Do not scan a QR code to receive money."],
    },
    {
        "title": "Phishing",
        "description": "Fake messages and websites imitate banks to steal personal information.",
        "do": ["Type the official website address yourself.", "Verify messages through official channels."],
        "dont": ["Do not click unexpected links.", "Do not install apps sent by strangers."],
    },
    {
        "title": "Fake bank calls",
        "description": "A caller may threaten to block an account unless you act immediately.",
        "do": ["End the call and contact the bank independently.", "Ask a trusted person for help if unsure."],
        "dont": ["Never share your PIN or password.", "Never install remote-access apps at a caller's request."],
    },
]

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=SESSION_TIMEOUT_MINUTES),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)


def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            dob TEXT NOT NULL DEFAULT '',
            mobile TEXT NOT NULL,
            email TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'English',
            accessibility TEXT NOT NULL DEFAULT '',
            bank_name TEXT NOT NULL DEFAULT '',
            security_question TEXT NOT NULL,
            security_answer_hash TEXT NOT NULL,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS guardians (
            user_id INTEGER PRIMARY KEY,
            guardian_name TEXT NOT NULL,
            relationship TEXT NOT NULL,
            contact TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS preferences (
            user_id INTEGER PRIMARY KEY,
            font_size INTEGER NOT NULL DEFAULT 18,
            high_contrast INTEGER NOT NULL DEFAULT 0,
            voice_enabled INTEGER NOT NULL DEFAULT 1,
            language TEXT NOT NULL DEFAULT 'English',
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        # A welcome/demo alert is created for newly registered users.
        db.commit()


def get_user_by_id(user_id):
    if not user_id:
        return None
    with db_connect() as db:
        return db.execute(
            "SELECT id, fullname, dob, mobile, email, username, language, accessibility, bank_name "
            "FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def get_user_by_username(username):
    with db_connect() as db:
        return db.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.strip(),)).fetchone()


def current_user():
    if "user_id" not in session:
        return None
    user = get_user_by_id(session.get("user_id"))
    if user is None:
        session.clear()
    return user


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def protect_requests_and_timeout():
    # Session inactivity timeout
    if session.get("user_id"):
        last = session.get("last_activity", time.time())
        if time.time() - float(last) > SESSION_TIMEOUT_MINUTES * 60:
            session.clear()
            flash("Your session expired after inactivity. Please log in again.", "warning")
            if request.endpoint not in ("login", "index", "fraud", "static"):
                return redirect(url_for("login"))
        else:
            session["last_activity"] = time.time()
            session.permanent = True

    # Synchronizer-token CSRF protection for all form/API POST requests.
    if request.method == "POST":
        supplied = request.form.get("_csrf") or request.headers.get("X-CSRF-Token", "")
        expected = session.get("_csrf", "")
        if not expected or not supplied or not hmac.compare_digest(str(supplied), str(expected)):
            abort(400, description="This form expired or could not be verified. Refresh the page and try again.")


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )
    return response


@app.context_processor
def inject_globals():
    user = current_user()
    pref = get_preferences(user["id"]) if user else default_preferences()
    return {
        "active_user": user,
        "preferences": pref,
        "demo_warning": "DEMONSTRATION ONLY — sample data; no real bank connection or payments.",
        "now_year": datetime.now().year,
    }


def default_preferences():
    return {"font_size": 18, "high_contrast": False, "voice_enabled": True, "language": "English"}


def get_preferences(user_id):
    with db_connect() as db:
        row = db.execute("SELECT * FROM preferences WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        return default_preferences()
    return {
        "font_size": row["font_size"], "high_contrast": bool(row["high_contrast"]),
        "voice_enabled": bool(row["voice_enabled"]), "language": row["language"],
    }


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id") or not get_user_by_id(session.get("user_id")):
            session.clear()
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def password_problems(password):
    problems = []
    if len(password) < 8: problems.append("at least 8 characters")
    if not re.search(r"[A-Z]", password): problems.append("an uppercase letter")
    if not re.search(r"[a-z]", password): problems.append("a lowercase letter")
    if not re.search(r"\d", password): problems.append("a number")
    if not re.search(r"[^A-Za-z0-9]", password): problems.append("a special character")
    return problems


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        dob = request.form.get("dob", "").strip()
        mobile = request.form.get("mobile", "").strip()
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        language = request.form.get("language", "English")
        accessibility_items = [x for x in request.form.getlist("accessibility") if x in ACCESS_OPTIONS]
        question = request.form.get("security_question", "")
        answer = re.sub(r"\s+", " ", request.form.get("security_answer", "").strip().lower())
        demo_biometrics_ack = request.form.get("demo_biometrics_ack") == "yes"
        errors = []
        if len(fullname) < 3 or len(fullname) > 80:
            errors.append("Enter your full name (3–80 characters).")
        if dob and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dob):
            errors.append("Enter a valid date of birth.")
        if not re.fullmatch(r"[6-9]\d{9}", mobile):
            errors.append("Enter a valid 10-digit Indian mobile number.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Enter a valid email address.")
        if not re.fullmatch(r"[A-Za-z0-9_.]{4,20}", username):
            errors.append("Username must be 4–20 letters, numbers, dots or underscores.")
        errors.extend(["Password needs " + ", ".join(password_problems(password)) + "."] if password_problems(password) else [])
        if password != confirm:
            errors.append("Passwords do not match.")
        if not accessibility_items:
            errors.append("Choose an accessibility option or 'Prefer not to disclose'.")
        if question not in SECURITY_QUESTIONS or len(answer) < 2:
            errors.append("Choose a security question and provide an answer.")
        if not demo_biometrics_ack:
            errors.append("Please acknowledge that biometric checks are simulated only.")
        if errors:
            for err in errors: flash(err, "error")
            return render_template("register.html", access_options=ACCESS_OPTIONS,
                                   banks=BANKS, questions=SECURITY_QUESTIONS, languages=LANGUAGES)
        try:
            with db_connect() as db:
                cur = db.execute("""
                    INSERT INTO users(fullname,dob,mobile,email,username,password_hash,language,
                                      accessibility,security_question,security_answer_hash)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                """, (fullname, dob, mobile, email, username,
                      generate_password_hash(password, method="scrypt"), language,
                      ", ".join(accessibility_items), question,
                      generate_password_hash(answer, method="scrypt")))
                uid = cur.lastrowid
                db.execute("INSERT INTO preferences(user_id, language) VALUES(?,?)", (uid, language))
                db.execute(
                    "INSERT INTO alerts(user_id,title,body,severity) VALUES(?,?,?,?)",
                    (uid, "Welcome to the demo", "This alert is sample content. No real banking events are monitored.", "info"),
                )
            flash("Account created successfully. This is a prototype account, not a bank account. Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That username is already registered. Choose another username.", "error")
    return render_template("register.html", access_options=ACCESS_OPTIONS,
                           banks=BANKS, questions=SECURITY_QUESTIONS, languages=LANGUAGES)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_username(username) if username else None
        if user and user["locked_until"]:
            try:
                locked_until = datetime.fromisoformat(user["locked_until"])
                if locked_until > datetime.now():
                    flash("This account is temporarily locked after too many failed attempts. Try again later.", "error")
                    return render_template("login.html")
            except ValueError:
                pass
        if user and check_password_hash(user["password_hash"], password):
            with db_connect() as db:
                db.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?", (user["id"],))
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["last_activity"] = time.time()
            session.permanent = True
            csrf_token()
            flash("Welcome back. Remember: this is a demonstration prototype.", "success")
            return redirect(url_for("dashboard"))
        if user:
            attempts = int(user["failed_attempts"]) + 1
            with db_connect() as db:
                if attempts >= MAX_LOGIN_ATTEMPTS:
                    until = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).isoformat()
                    db.execute("UPDATE users SET failed_attempts=0, locked_until=? WHERE id=?", (until, user["id"]))
                else:
                    db.execute("UPDATE users SET failed_attempts=? WHERE id=?", (attempts, user["id"]))
            if attempts >= MAX_LOGIN_ATTEMPTS:
                flash(f"Too many failed attempts. Account locked for {LOCK_MINUTES} minutes.", "error")
            else:
                flash(f"Incorrect username or password. {MAX_LOGIN_ATTEMPTS - attempts} attempt(s) remaining before temporary lock.", "error")
        else:
            # Generic response avoids revealing whether the username exists.
            flash("Incorrect username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    cooldown_until = float(session.get("recovery_cooldown_until", 0))
    if time.time() < cooldown_until:
        flash("Password recovery is temporarily paused after repeated failed checks. Please wait 15 minutes.", "error")
        return render_template("forgot.html", questions=SECURITY_QUESTIONS)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = get_user_by_username(username) if username else None
        question = request.form.get("security_question", "")
        answer = re.sub(r"\s+", " ", request.form.get("security_answer", "").strip().lower())
        verified = bool(user and question == user["security_question"] and
                        check_password_hash(user["security_answer_hash"], answer))
        if not verified:
            attempts = int(session.get("recovery_failed_attempts", 0)) + 1
            session["recovery_failed_attempts"] = attempts
            if attempts >= 3:
                session["recovery_cooldown_until"] = time.time() + LOCK_MINUTES * 60
                session["recovery_failed_attempts"] = 0
                flash("Too many failed recovery checks. Please wait 15 minutes before trying again.", "error")
            else:
                flash("We could not verify those details. Check the username, question and answer.", "error")
            return render_template("forgot.html", questions=SECURITY_QUESTIONS)
        session.pop("recovery_failed_attempts", None)
        session.pop("recovery_cooldown_until", None)
        session["reset_user_id"] = user["id"]
        session["reset_expires"] = time.time() + 300
        flash("Identity check passed for this demo. Choose a new password.", "success")
        return redirect(url_for("reset_password"))
    return render_template("forgot.html", questions=SECURITY_QUESTIONS)


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    uid = session.get("reset_user_id")
    if not uid or time.time() > float(session.get("reset_expires", 0)):
        session.pop("reset_user_id", None)
        session.pop("reset_expires", None)
        flash("Password reset session expired. Start again.", "warning")
        return redirect(url_for("forgot"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        problems = password_problems(password)
        if problems or password != confirm:
            if problems: flash("Password needs " + ", ".join(problems) + ".", "error")
            if password != confirm: flash("Passwords do not match.", "error")
            return render_template("reset_password.html")
        with db_connect() as db:
            db.execute("UPDATE users SET password_hash=?, failed_attempts=0, locked_until=NULL WHERE id=?",
                       (generate_password_hash(password, method="scrypt"), uid))
        session.pop("reset_user_id", None)
        session.pop("reset_expires", None)
        flash("Password changed. Please log in with your new password.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html")


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    with db_connect() as db:
        alerts = db.execute("SELECT * FROM alerts WHERE user_id=? ORDER BY id DESC LIMIT 5", (user["id"],)).fetchall()
        guardian = db.execute("SELECT * FROM guardians WHERE user_id=?", (user["id"],)).fetchone()
    return render_template("dashboard.html", user=user, balance=DEMO_BALANCE,
                           transactions=SAMPLE_TRANSACTIONS, alerts=alerts, guardian=guardian)


@app.route("/bank", methods=["GET", "POST"])
@login_required
def bank():
    if request.method == "POST":
        bank_name = request.form.get("bank_name", "")
        sample_account = request.form.get("account_number", "").strip()
        if bank_name not in BANKS:
            flash("Choose a bank from the list.", "error")
        elif not re.fullmatch(r"\d{9,18}", sample_account):
            flash("For this simulation, enter 9–18 digits. Do not enter a real account number.", "error")
        else:
            with db_connect() as db:
                db.execute("UPDATE users SET bank_name=? WHERE id=?", (bank_name, session["user_id"]))
                db.execute("INSERT INTO alerts(user_id,title,body,severity) VALUES(?,?,?,?)",
                           (session["user_id"], "Demo bank linked", f"{bank_name} was selected in simulation only. No account was accessed.", "info"))
            flash("Bank selected in simulation only. The account number was not saved and no bank was contacted.", "success")
            return redirect(url_for("dashboard"))
    return render_template("bank.html", banks=BANKS, user=current_user())


@app.route("/guardian", methods=["GET", "POST"])
@login_required
def guardian():
    with db_connect() as db:
        existing = db.execute("SELECT * FROM guardians WHERE user_id=?", (session["user_id"],)).fetchone()
    if request.method == "POST":
        name = request.form.get("guardian_name", "").strip()
        relationship = request.form.get("relationship", "Other")
        contact = request.form.get("contact", "").strip()
        if len(name) < 2 or len(name) > 80 or relationship not in ["Family member", "Friend", "Caregiver", "Other"] or not re.fullmatch(r"[6-9]\d{9}", contact):
            flash("Enter a name, relationship and valid 10-digit Indian mobile number.", "error")
        else:
            with db_connect() as db:
                db.execute("""INSERT INTO guardians(user_id,guardian_name,relationship,contact)
                    VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                    guardian_name=excluded.guardian_name, relationship=excluded.relationship, contact=excluded.contact""",
                    (session["user_id"], name, relationship, contact))
            flash("Trusted person details saved on this device. No message has been sent to them.", "success")
            return redirect(url_for("dashboard"))
    return render_template("guardian.html", guardian=existing)


@app.route("/fraud")
def fraud():
    return render_template("fraud.html", topics=FRAUD_TOPICS)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = current_user()
    if request.method == "POST":
        try:
            font_size = int(request.form.get("font_size", "18"))
        except ValueError:
            font_size = 18
        font_size = max(16, min(32, font_size))
        contrast = 1 if request.form.get("high_contrast") == "on" else 0
        voice = 1 if request.form.get("voice_enabled") == "on" else 0
        language = request.form.get("language", "English")
        if language not in LANGUAGES:
            language = "English"
        with db_connect() as db:
            db.execute("""INSERT INTO preferences(user_id,font_size,high_contrast,voice_enabled,language)
                VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                font_size=excluded.font_size, high_contrast=excluded.high_contrast,
                voice_enabled=excluded.voice_enabled, language=excluded.language""",
                (user["id"], font_size, contrast, voice, language))
            db.execute("UPDATE users SET language=? WHERE id=?", (language, user["id"]))
        flash("Accessibility settings saved.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", languages=LANGUAGES)


@app.route("/alerts")
@login_required
def alerts():
    with db_connect() as db:
        rows = db.execute("SELECT * FROM alerts WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    return render_template("alerts.html", alerts=rows)


@app.route("/alerts/read", methods=["POST"])
@login_required
def mark_alerts_read():
    with db_connect() as db:
        db.execute("UPDATE alerts SET is_read=1 WHERE user_id=?", (session["user_id"],))
    flash("Demo alerts marked as read.", "success")
    return redirect(url_for("alerts"))


@app.route("/api/assistant", methods=["POST"])
@login_required
def assistant():
    data = request.get_json(silent=True) or {}
    command = str(data.get("command", ""))[:500].lower().strip()
    if any(k in command for k in ["balance", "இருப்பு", "बैलेंस", "शेष"]):
        reply = f"Your available demonstration balance is ₹{DEMO_BALANCE:,.2f}."
    elif any(k in command for k in ["transaction", "பரிவர்த்தனை", "लेन"]):
        reply = "Recent sample transactions: " + "; ".join(
            f"{x['type']} ₹{x['amount']:.2f} for {x['description']} on {x['date']}" for x in SAMPLE_TRANSACTIONS
        )
    elif any(k in command for k in ["fraud", "safety", "tip", "பாதுகாப்பு", "सुरक्षा"]):
        reply = "Never share your OTP, PIN or password. Banks will not ask you to reveal these. Verify callers through official channels."
    elif "bill" in command or "payment" in command:
        reply = "Payments are not connected. This prototype will not make any payment."
    elif any(k in command for k in ["dashboard", "home", "முகப்பு", "डैशबोर्ड"]):
        reply = "You are on the dashboard. Use the navigation to view your sample balance and transactions."
    elif "help" in command:
        reply = "Try: check balance, recent transactions, safety tips, or bill payment status."
    else:
        reply = "I did not understand. Try: Check Balance, Recent Transactions, or Safety Tips."
    return jsonify({"reply": reply})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "mode": "prototype", "real_banking_connected": False})


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400,
                           message=getattr(error, "description", "The request could not be verified.")), 400


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="That page could not be found."), 404


@app.errorhandler(500)
def server_error(_error):
    return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500


init_db()

if __name__ == "__main__":
    # Local development only. For deployment, use a production WSGI server.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
