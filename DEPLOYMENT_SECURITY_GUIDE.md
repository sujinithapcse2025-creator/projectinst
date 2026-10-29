# Testing, security and deployment guide

## 1. Run locally on Windows

Open Command Prompt in this folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
python app.py
```

If PowerShell blocks activation, you can use Command Prompt instead:

```bat
.venv\Scripts\activate.bat
```

Open `http://127.0.0.1:5000`. Use fictional test details only.

## 2. Manual application test checklist

- [ ] Home, registration, login, fraud-awareness and password-recovery pages load.
- [ ] Registration rejects missing/invalid fields and mismatched passwords.
- [ ] Registration rejects a duplicate username.
- [ ] Passwords and security answers are stored as hashes, not plain text.
- [ ] Correct login succeeds; incorrect login fails; repeated failures trigger temporary lockout.
- [ ] Dashboard, settings, alerts, guardian and bank pages redirect when logged out.
- [ ] Logged-in user can save/reload accessibility settings.
- [ ] Trusted-person details persist and belong only to the logged-in user.
- [ ] POST requests without a valid CSRF token are rejected.
- [ ] Logout ends the session; inactivity timeout returns the user to login.
- [ ] Try on mobile-sized screens, keyboard-only navigation, browser zoom, high contrast and screen readers.
- [ ] Confirm every screen clearly states that balances, transactions, bank linking and payments are simulated.
- [ ] Verify the app does not ask for or store real bank passwords, PINs, OTPs or account credentials.

The included automated tests are basic smoke/regression tests, not a full security audit or penetration test.

## 3. Security settings before hosting

Generate a strong secret key locally with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

In your hosting provider's **environment variables / secrets** settings, set:

- `SECRET_KEY` = the generated random value (keep it private; do not commit it).
- `COOKIE_SECURE` = `1` only when the app is served over HTTPS.
- `BANKING_DB_PATH` = a location on persistent storage if you use SQLite in hosting.

Other safeguards already present in the prototype include password hashing, CSRF token checks, basic response security headers, a short inactivity timeout, and account lockout after failed logins. These are helpful baseline controls, not a guarantee of production security.

Additional work needed before real users or real financial data: independent security review, stronger rate limiting (including IP/device-level limits), secure and verified account recovery, audit logging and monitoring, privacy/retention policy, backup/restore testing, accessibility testing with disabled users, HTTPS, and an approved real banking integration. Do not use this prototype for real transactions.

## 4. Deploy as a web app (example: Render)

1. Put the project in a private Git repository, excluding `.env`, local database files and secrets. Review `.gitignore` first.
2. Create a new **Web Service** from that repository in your hosting provider.
3. Set the build/install command to `pip install -r requirements.txt`.
4. Set the start command to `gunicorn --workers 2 --timeout 60 --access-logfile - --error-logfile - app:app`.
5. Add the environment variables described above in the provider dashboard. Never put secret values in source code or a public repository.
6. Configure persistent storage for `banking_companion.db` and set `BANKING_DB_PATH` to that mounted path. Without persistent storage, a local SQLite file may be lost on redeploy/restart; SQLite is also not ideal for multi-instance production use.
7. Enable HTTPS and confirm the provider redirects HTTP to HTTPS before setting `COOKIE_SECURE=1`.
8. After deployment, open `/health`, then test registration, login, logout, settings and the CSRF rejection. Use only fictional data.
9. Check provider logs and test backup/restore before sharing the demo.

For a larger or real service, use a managed database such as PostgreSQL instead of a local SQLite file and obtain a professional security/compliance review. This prototype is for demonstration only, not production banking software.
