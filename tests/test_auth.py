import pytest

import database.db as db

NAME = "Ada Lovelace"
EMAIL = "ada@example.com"
PASSWORD = "correcthorse1"
LOGIN_ERROR = "Invalid email or password."


@pytest.fixture
def user(app):
    return db.create_user(NAME, EMAIL, PASSWORD)


def post_login(client, email=EMAIL, password=PASSWORD, **kwargs):
    return client.post("/login", data={"email": email, "password": password},
                       **kwargs)


def test_get_login_renders_form(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "<form" in resp.get_data(as_text=True)


def test_valid_login_redirects_to_profile(client, user):
    resp = post_login(client)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"


def test_valid_login_sets_session(client, user):
    post_login(client)
    with client.session_transaction() as sess:
        assert sess["user_id"] == user
        assert sess["user_name"] == NAME
        assert set(sess.keys()) == {"user_id", "user_name"}


def test_login_email_is_normalised(client, user):
    resp = post_login(client, email="  ADA@Example.com ")
    assert resp.status_code == 302


def test_navbar_shows_user_after_login(client, user):
    post_login(client)
    body = client.get("/").get_data(as_text=True)
    assert NAME in body
    assert "Sign out" in body
    assert "Get started" not in body


def test_wrong_password(client, user):
    resp = post_login(client, password="wrongpassword")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 401
    assert LOGIN_ERROR in body
    assert f'value="{EMAIL}"' in body
    assert "wrongpassword" not in body


def test_unknown_email(client, user):
    resp = post_login(client, email="nobody@example.com")
    assert resp.status_code == 401
    assert LOGIN_ERROR in resp.get_data(as_text=True)


@pytest.mark.parametrize("email,password", [("", PASSWORD), (EMAIL, "")])
def test_empty_fields(client, user, email, password):
    resp = post_login(client, email=email, password=password)
    assert resp.status_code == 401
    assert LOGIN_ERROR in resp.get_data(as_text=True)


def test_failed_login_sets_no_session(client, user):
    post_login(client, password="wrongpassword")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_clears_session_and_flashes(client, user):
    post_login(client)
    resp = client.get("/logout", follow_redirects=True)
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert resp.request.path == "/"
    assert "You have been signed out." in body
    assert "Sign in" in body
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_when_not_logged_in(client):
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_logged_in_user_redirected_from_auth_pages(client, user, path):
    post_login(client)
    resp = client.get(path)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"


def test_register_then_login(client):
    client.post("/register", data={"name": NAME, "email": EMAIL,
                                   "password": PASSWORD})
    resp = post_login(client)
    assert resp.status_code == 302


def test_registration_flash_shown_once(client):
    resp = client.post("/register", data={"name": NAME, "email": EMAIL,
                                          "password": PASSWORD},
                       follow_redirects=True)
    body = resp.get_data(as_text=True)
    assert body.count("Account created — please sign in.") == 1


def test_authenticate_user(app, user):
    assert db.authenticate_user(EMAIL, PASSWORD)["id"] == user
    assert db.authenticate_user(EMAIL, "wrongpassword") is None
    assert db.authenticate_user("nobody@example.com", PASSWORD) is None
