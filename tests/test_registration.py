import sys

from werkzeug.security import check_password_hash

import database.db as db

VALID = {
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "password": "correcthorse1",
}
DUPLICATE_ERROR = "An account with that email already exists."


def post_register(client, **overrides):
    return client.post("/register", data={**VALID, **overrides})


def test_get_register_renders_form(client):
    resp = client.get("/register")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "<form" in body
    assert 'name="email"' in body


def test_valid_post_redirects_to_login(client):
    resp = post_register(client)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"


def test_valid_post_stores_hashed_password(client):
    post_register(client)
    row = db.get_user_by_email(VALID["email"])
    assert row is not None
    assert row["name"] == VALID["name"]
    assert row["password_hash"] != VALID["password"]
    assert check_password_hash(row["password_hash"], VALID["password"])


def test_success_flash_shown_on_login(client):
    resp = client.post("/register", data=VALID, follow_redirects=True)
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'class="auth-success"' in body
    assert "Account created — please sign in." in body


def test_email_is_lowercased(client):
    post_register(client, email="  Demo@Example.com ")
    assert db.get_user_by_email("demo@example.com") is not None


def test_duplicate_email_rejected(client, user_count):
    post_register(client)
    before = user_count()
    resp = post_register(client)
    assert resp.status_code == 400
    assert DUPLICATE_ERROR in resp.get_data(as_text=True)
    assert user_count() == before


def test_duplicate_email_case_insensitive(client, user_count):
    post_register(client)
    before = user_count()
    resp = post_register(client, email="ADA@Example.COM")
    assert resp.status_code == 400
    assert DUPLICATE_ERROR in resp.get_data(as_text=True)
    assert user_count() == before


def test_missing_name(client, user_count):
    before = user_count()
    resp = post_register(client, name="   ")
    assert resp.status_code == 400
    assert "Please enter your name." in resp.get_data(as_text=True)
    assert user_count() == before


def test_name_field_omitted(client, user_count):
    before = user_count()
    data = {k: v for k, v in VALID.items() if k != "name"}
    resp = client.post("/register", data=data)
    assert resp.status_code == 400
    assert "Please enter your name." in resp.get_data(as_text=True)
    assert user_count() == before


def test_only_first_error_reported(client):
    resp = post_register(client, name="", email="bad", password="short")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 400
    assert "Please enter your name." in body
    assert "Please enter a valid email address." not in body
    assert "Password must be at least 8 characters." not in body


def test_name_over_100_chars(client):
    resp = post_register(client, name="a" * 101)
    assert resp.status_code == 400
    assert "Please enter your name." in resp.get_data(as_text=True)


def test_invalid_email(client, user_count):
    before = user_count()
    resp = post_register(client, email="not-an-email")
    assert resp.status_code == 400
    assert "Please enter a valid email address." in resp.get_data(as_text=True)
    assert user_count() == before


def test_short_password(client, user_count):
    before = user_count()
    resp = post_register(client, password="abcdefg")
    assert resp.status_code == 400
    assert "Password must be at least 8 characters." in resp.get_data(as_text=True)
    assert user_count() == before


def test_error_rerender_keeps_name_email_not_password(client):
    resp = post_register(client, email="not-an-email", password="UniquePw12345")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 400
    assert 'value="Ada Lovelace"' in body
    assert 'value="not-an-email"' in body
    assert "UniquePw12345" not in body


def test_create_user_race_returns_400(client, monkeypatch, user_count):
    db.create_user(VALID["name"], VALID["email"], VALID["password"])
    monkeypatch.setattr(sys.modules["app"], "get_user_by_email", lambda email: None)
    before = user_count()
    resp = post_register(client)
    assert resp.status_code == 400
    assert DUPLICATE_ERROR in resp.get_data(as_text=True)
    assert user_count() == before


def test_create_user_duplicate_returns_none(app):
    assert db.create_user("A", "dup@example.com", "password1") is not None
    assert db.create_user("B", "dup@example.com", "password2") is None
