import importlib
import sqlite3

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_banking.db"
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app_module.init_db()
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-only-secret-key")
    with app_module.app.test_client() as test_client:
        yield test_client


def set_csrf(client, token="test-csrf-token"):
    with client.session_transaction() as sess:
        sess["_csrf"] = token
    return token


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.get_json()["real_banking_connected"] is False


def test_public_pages_load(client):
    for path in ("/", "/login", "/register", "/fraud", "/forgot"):
        response = client.get(path)
        assert response.status_code == 200, path


def test_private_pages_redirect_to_login(client):
    for path in ("/dashboard", "/settings", "/alerts", "/guardian", "/bank"):
        response = client.get(path)
        assert response.status_code == 302, path
        assert "/login" in response.headers["Location"]


def test_post_without_csrf_is_rejected(client):
    response = client.post("/login", data={"username": "nobody", "password": "bad"})
    assert response.status_code == 400


def test_registration_login_and_dashboard(client, tmp_path, monkeypatch):
    token = set_csrf(client)
    response = client.post("/register", data={
        "_csrf": token,
        "fullname": "Demo Person",
        "dob": "2000-01-01",
        "mobile": "9876543210",
        "email": "demo@example.test",
        "username": "demo_user",
        "language": "English",
        "accessibility": "Prefer not to disclose",
        "password": "DemoPass!234",
        "confirm_password": "DemoPass!234",
        "security_question": "What is your favorite city?",
        "security_answer": "Chennai Demo",
        "demo_biometrics_ack": "yes",
    }, follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    # Successful registration must persist a user record in the configured test DB.
    db_path = app_module.DB_PATH
    with sqlite3.connect(db_path) as db:
        row = db.execute("SELECT username, password_hash FROM users WHERE username=?", ("demo_user",)).fetchone()
    assert row is not None
    assert row[0] == "demo_user"
    assert row[1] != "DemoPass!234"

    token = set_csrf(client, "login-csrf-token")
    response = client.post("/login", data={
        "_csrf": token,
        "username": "demo_user",
        "password": "DemoPass!234",
    }, follow_redirects=False)
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"DEMONSTRATION ONLY" in response.data or b"demonstration" in response.data.lower()
