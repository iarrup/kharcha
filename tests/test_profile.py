import importlib
import re
from pathlib import Path

import pytest

import database.db as db

ROOT = Path(__file__).parents[1]
TEMPLATE = ROOT / "templates" / "profile.html"
STYLESHEET = ROOT / "static" / "css" / "profile.css"
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
NAV_NAME = "Ada Lovelace"


@pytest.fixture
def profile_mod(app):
    # Import lazily: importing app runs init_db()/seed_db(), which must hit
    # the temp DB that the `app` fixture has already patched in.
    return importlib.import_module("app")


@pytest.fixture
def logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = NAV_NAME
    return client


def get_profile_body(client):
    resp = client.get("/profile")
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


# ------------------------------------------------------------------ #
# Access                                                              #
# ------------------------------------------------------------------ #

def test_profile_redirects_when_logged_out(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"


def test_profile_200_when_logged_in(logged_in):
    assert logged_in.get("/profile").status_code == 200


# ------------------------------------------------------------------ #
# Page content                                                        #
# ------------------------------------------------------------------ #

def test_user_card(logged_in, profile_mod):
    body = get_profile_body(logged_in)
    user = profile_mod.PROFILE_USER
    assert user["name"] in body
    assert user["email"] in body
    assert "Member since" in body
    assert f">{user['initials']}<" in body


def test_summary_stats(logged_in):
    body = get_profile_body(logged_in)
    assert "₹11,000.00" in body
    assert "Transactions" in body
    assert "Top category" in body
    assert "Food" in body


def test_transaction_rows(logged_in, profile_mod):
    rows = get_profile_body(logged_in).count('class="profile-table__row"')
    assert rows == len(profile_mod.PROFILE_EXPENSES)
    assert rows >= 3


def test_category_breakdown(logged_in):
    items = get_profile_body(logged_in).count('class="profile-breakdown__item"')
    assert items == 7


def test_navbar_logged_in_state(logged_in):
    body = get_profile_body(logged_in)
    assert NAV_NAME in body
    assert "Sign out" in body
    assert "Get started" not in body


def test_badges_use_classes_not_inline_styles(logged_in):
    body = get_profile_body(logged_in)
    assert "profile-badge--food" in body
    assert "style=" not in body


def test_page_links_profile_stylesheet(logged_in):
    assert "css/profile.css" in get_profile_body(logged_in)


def test_profile_route_makes_no_db_calls(logged_in, monkeypatch):
    def fail():
        raise AssertionError("profile route must not touch the DB")

    monkeypatch.setattr(db, "get_db", fail)
    assert logged_in.get("/profile").status_code == 200


# ------------------------------------------------------------------ #
# Style rules                                                         #
# ------------------------------------------------------------------ #

def test_no_hex_colours_in_template_or_css():
    assert not HEX_RE.search(TEMPLATE.read_text())
    assert not HEX_RE.search(STYLESHEET.read_text())


def test_every_category_has_a_badge_style():
    css = STYLESHEET.read_text()
    for name in db.CATEGORIES:
        assert f".profile-badge--{name.lower()}" in css


# ------------------------------------------------------------------ #
# summarize_expenses                                                  #
# ------------------------------------------------------------------ #

def test_summarize_expenses_sample_data(profile_mod):
    summary = profile_mod.summarize_expenses(profile_mod.PROFILE_EXPENSES)
    categories = summary["categories"]
    amounts = [c["amount"] for c in categories]

    assert summary["total"] == pytest.approx(11000.0)
    assert summary["count"] == 8
    assert summary["top_category"]["name"] == "Food"
    assert sum(c["percent"] for c in categories) == 100
    assert amounts == sorted(amounts, reverse=True)
    for c in categories:
        assert c["bar_step"] % 5 == 0
        assert 5 <= c["bar_step"] <= 100


def test_summarize_expenses_empty(profile_mod):
    assert profile_mod.summarize_expenses([]) == {
        "total": 0, "count": 0, "top_category": None, "categories": [],
    }
