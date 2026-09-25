import importlib
import inspect
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

import database.db as db

ROOT = Path(__file__).parents[1]
TEMPLATE = ROOT / "templates" / "add_expense.html"
STYLESHEET = ROOT / "static" / "css" / "expense.css"
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")

NAME_A = "Ada Lovelace"
EMAIL_A = "ada@example.com"
PASSWORD_A = "correcthorse1"

NAME_B = "Grace Hopper"
EMAIL_B = "grace@example.com"
PASSWORD_B = "anotherpass1"

AMOUNT_ERROR = "Please enter an amount greater than 0."
CATEGORY_ERROR = "Please choose a valid category."
DATE_ERROR = "Please enter a valid date."
FUTURE_ERROR = "Date can&#39;t be in the future."
DESCRIPTION_ERROR = "Description must be 200 characters or fewer."


@pytest.fixture
def app_mod(app):
    # Import lazily so init_db()/seed_db() hit the temp DB the `app`
    # fixture has already patched in.
    return importlib.import_module("app")


@pytest.fixture
def user_a(app):
    return db.create_user(NAME_A, EMAIL_A, PASSWORD_A)


@pytest.fixture
def logged_in(client, user_a):
    client.post("/login", data={"email": EMAIL_A, "password": PASSWORD_A})
    return client


def expense_rows(user_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchall()
    finally:
        conn.close()


def all_expense_rows():
    conn = db.get_db()
    try:
        return conn.execute("SELECT * FROM expenses").fetchall()
    finally:
        conn.close()


def valid_form(**overrides):
    form = {
        "amount": "250.00",
        "category": "Food",
        "date": date.today().isoformat(),
        "description": "Lunch",
    }
    form.update(overrides)
    return form


# ------------------------------------------------------------------ #
# Auth guards                                                         #
# ------------------------------------------------------------------ #

def test_get_redirects_when_logged_out(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"


def test_post_redirects_when_logged_out_and_inserts_nothing(client):
    resp = client.post("/expenses/add", data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"
    assert all_expense_rows() == []


# ------------------------------------------------------------------ #
# GET form rendering                                                  #
# ------------------------------------------------------------------ #

def test_get_form_shows_all_categories(logged_in):
    body = logged_in.get("/expenses/add").get_data(as_text=True)
    assert logged_in.get("/expenses/add").status_code == 200
    for category in db.CATEGORIES:
        assert f'value="{category}"' in body


def test_get_form_defaults_to_today(logged_in):
    body = logged_in.get("/expenses/add").get_data(as_text=True)
    assert f'value="{date.today().isoformat()}"' in body


def test_get_form_has_cancel_link_to_profile(logged_in):
    body = logged_in.get("/expenses/add").get_data(as_text=True)
    assert re.search(r'href="/profile"\s+class="btn-ghost">Cancel<', body)


def test_get_form_links_expense_stylesheet(logged_in):
    body = logged_in.get("/expenses/add").get_data(as_text=True)
    assert "css/expense.css" in body


def test_profile_has_add_expense_link(logged_in):
    body = logged_in.get("/profile").get_data(as_text=True)
    assert re.search(r'href="/expenses/add"[^>]*>Add expense<', body)


# ------------------------------------------------------------------ #
# Happy path                                                          #
# ------------------------------------------------------------------ #

def test_valid_post_redirects_to_profile(logged_in):
    resp = logged_in.post("/expenses/add", data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"


def test_valid_post_flashes_and_stores_row(logged_in, user_a):
    resp = logged_in.post("/expenses/add", data=valid_form(), follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Expense added." in body

    rows = expense_rows(user_a)
    assert len(rows) == 1
    row = rows[0]
    assert row["amount"] == pytest.approx(250.00)
    assert row["category"] == "Food"
    assert row["date"] == date.today().isoformat()
    assert row["description"] == "Lunch"


def test_valid_post_updates_profile_totals(logged_in, user_a):
    db.seed_db()
    logged_in.post("/login", data={"email": EMAIL_A, "password": PASSWORD_A})
    logged_in.post("/expenses/add", data=valid_form(amount="250.00"))
    body = logged_in.get("/profile").get_data(as_text=True)
    assert "₹250.00" in body
    assert '<p class="profile-stat__value">1</p>' in body


def test_demo_user_totals_after_add(client, app):
    db.seed_db()
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    client.post("/expenses/add", data=valid_form(amount="250.00"))
    body = client.get("/profile").get_data(as_text=True)
    assert "₹538.24" in body
    assert '<p class="profile-stat__value">9</p>' in body


def test_blank_description_stored_as_null(logged_in, user_a):
    logged_in.post("/expenses/add", data=valid_form(description=""))
    rows = expense_rows(user_a)
    assert len(rows) == 1
    assert rows[0]["description"] is None


def test_whitespace_description_stored_as_null(logged_in, user_a):
    logged_in.post("/expenses/add", data=valid_form(description="   "))
    rows = expense_rows(user_a)
    assert len(rows) == 1
    assert rows[0]["description"] is None


# ------------------------------------------------------------------ #
# Amount validation                                                   #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize(
    "amount", ["0", "-5", "abc", "nan", "inf", "", "0.004"]
)
def test_invalid_amount_returns_400_and_inserts_nothing(logged_in, user_a, amount):
    resp = logged_in.post("/expenses/add", data=valid_form(amount=amount))
    assert resp.status_code == 400
    assert AMOUNT_ERROR in resp.get_data(as_text=True)
    assert expense_rows(user_a) == []


# ------------------------------------------------------------------ #
# Category validation                                                 #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("category", ["Crypto", "", "food"])
def test_invalid_category_returns_400_and_inserts_nothing(logged_in, user_a, category):
    resp = logged_in.post("/expenses/add", data=valid_form(category=category))
    assert resp.status_code == 400
    assert CATEGORY_ERROR in resp.get_data(as_text=True)
    assert expense_rows(user_a) == []


# ------------------------------------------------------------------ #
# Date validation                                                     #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("bad_date", ["2026-02-30", "abc", "", "20260101"])
def test_invalid_date_returns_400_and_inserts_nothing(logged_in, user_a, bad_date):
    resp = logged_in.post("/expenses/add", data=valid_form(date=bad_date))
    assert resp.status_code == 400
    assert DATE_ERROR in resp.get_data(as_text=True)
    assert expense_rows(user_a) == []


def test_future_date_returns_400_with_future_error(logged_in, user_a):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    resp = logged_in.post("/expenses/add", data=valid_form(date=tomorrow))
    assert resp.status_code == 400
    assert FUTURE_ERROR in resp.get_data(as_text=True)
    assert expense_rows(user_a) == []


def test_today_date_succeeds(logged_in, user_a):
    resp = logged_in.post("/expenses/add", data=valid_form(date=date.today().isoformat()))
    assert resp.status_code == 302
    assert len(expense_rows(user_a)) == 1


# ------------------------------------------------------------------ #
# Description validation                                              #
# ------------------------------------------------------------------ #

def test_description_exactly_200_chars_succeeds(logged_in, user_a):
    description = "x" * 200
    resp = logged_in.post("/expenses/add", data=valid_form(description=description))
    assert resp.status_code == 302
    rows = expense_rows(user_a)
    assert len(rows) == 1
    assert rows[0]["description"] == description


def test_description_201_chars_fails(logged_in, user_a):
    description = "x" * 201
    resp = logged_in.post("/expenses/add", data=valid_form(description=description))
    assert resp.status_code == 400
    assert DESCRIPTION_ERROR in resp.get_data(as_text=True)
    assert expense_rows(user_a) == []


# ------------------------------------------------------------------ #
# Form values kept after a validation error                           #
# ------------------------------------------------------------------ #

def test_form_keeps_submitted_values_after_error(logged_in):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    resp = logged_in.post(
        "/expenses/add",
        data={
            "amount": "-5",
            "category": "Bills",
            "date": yesterday,
            "description": "Bad amount test",
        },
    )
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert 'value="-5"' in body
    assert f'value="{yesterday}"' in body
    assert "Bad amount test" in body
    assert re.search(r'value="Bills"\s*\n?\s*selected>Bills<', body) or \
        re.search(r'value="Bills"[^>]*selected[^>]*>Bills<', body)


# ------------------------------------------------------------------ #
# Isolation between users                                             #
# ------------------------------------------------------------------ #

def test_other_user_does_not_see_expense(logged_in, user_a):
    logged_in.post("/expenses/add", data=valid_form())
    user_b = db.create_user(NAME_B, EMAIL_B, PASSWORD_B)
    client_b = logged_in
    client_b.get("/logout")
    client_b.post("/login", data={"email": EMAIL_B, "password": PASSWORD_B})
    body = client_b.get("/profile").get_data(as_text=True)
    assert '<p class="profile-stat__value">0</p>' in body
    assert expense_rows(user_b) == []


def test_injected_user_id_is_ignored(logged_in, user_a):
    user_b = db.create_user(NAME_B, EMAIL_B, PASSWORD_B)
    resp = logged_in.post("/expenses/add", data=valid_form(user_id=str(user_b)))
    assert resp.status_code == 302
    assert len(expense_rows(user_a)) == 1
    assert expense_rows(user_b) == []


# ------------------------------------------------------------------ #
# validate_expense unit tests                                         #
# ------------------------------------------------------------------ #

def test_validate_expense_rounds_amount(app_mod):
    data, error = app_mod.validate_expense({
        "amount": "12.345", "category": "Food",
        "date": date.today().isoformat(), "description": "",
    })
    assert error is None
    assert data["amount"] == pytest.approx(12.35)


def test_validate_expense_max_amount_boundary(app_mod):
    today = date.today().isoformat()
    data, error = app_mod.validate_expense({
        "amount": "10000000", "category": "Food",
        "date": today, "description": "",
    })
    assert error is None
    assert data["amount"] == pytest.approx(10000000.0)

    data, error = app_mod.validate_expense({
        "amount": "10000000.01", "category": "Food",
        "date": today, "description": "",
    })
    assert error == AMOUNT_ERROR
    assert data is None


def test_validate_expense_strips_description(app_mod):
    data, error = app_mod.validate_expense({
        "amount": "10", "category": "Food",
        "date": date.today().isoformat(), "description": "  Lunch  ",
    })
    assert error is None
    assert data["description"] == "Lunch"


# ------------------------------------------------------------------ #
# create_expense SQL hygiene                                          #
# ------------------------------------------------------------------ #

def test_create_expense_uses_placeholders_only():
    source = inspect.getsource(db.create_expense)
    assert "?" in source
    assert "%" not in source
    assert ".format(" not in source
    assert "f\"" not in source and "f'" not in source


# ------------------------------------------------------------------ #
# Style rules                                                         #
# ------------------------------------------------------------------ #

def test_no_hex_colours_in_template_or_css():
    assert not HEX_RE.search(TEMPLATE.read_text())
    assert not HEX_RE.search(STYLESHEET.read_text())


def test_no_inline_styles_in_template_or_css():
    assert "style=" not in TEMPLATE.read_text()
    assert "style=" not in STYLESHEET.read_text()


# ------------------------------------------------------------------ #
# Edit/delete stub routes stay untouched                              #
# ------------------------------------------------------------------ #

def test_edit_stub_still_responds(client):
    assert client.get("/expenses/1/edit").status_code == 200


def test_delete_stub_still_responds(client):
    assert client.get("/expenses/1/delete").status_code == 200
