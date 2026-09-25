import importlib
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

import database.db as db

ROOT = Path(__file__).parents[1]
TEMPLATE = ROOT / "templates" / "profile.html"
STYLESHEET = ROOT / "static" / "css" / "profile.css"
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
NAV_NAME = "Ada Lovelace"
EMAIL = "ada@example.com"
PASSWORD = "correcthorse1"

# (amount, category, date, description) — total 175.49, top category Bills.
SAMPLE_EXPENSES = [
    (45.50, "Food", "2026-09-02", "Groceries"),
    (89.99, "Bills", "2026-09-05", "Electricity bill"),
    (30.00, "Food", "2026-09-17", "Restaurant dinner"),
    (10.00, "Other", "2026-09-20", None),
]


@pytest.fixture
def profile_mod(app):
    # Import lazily: importing app runs init_db()/seed_db(), which must hit
    # the temp DB that the `app` fixture has already patched in.
    return importlib.import_module("app")


def add_expense(user_id, amount, category, date, description=None):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def user_id(app):
    # The first test to import `app` also gets the seeded demo user, so never
    # assume a particular id — always use the one create_user returns.
    return db.create_user(NAV_NAME, EMAIL, PASSWORD)


@pytest.fixture
def logged_in(client, user_id):
    client.post("/login", data={"email": EMAIL, "password": PASSWORD})
    return client


@pytest.fixture
def with_expenses(user_id):
    for expense in SAMPLE_EXPENSES:
        add_expense(user_id, *expense)


def get_profile_body(client, **params):
    resp = client.get("/profile", query_string=params)
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


def test_profile_stale_session_redirects_and_clears(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99999
        sess["user_name"] = "Ghost"
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"
    with client.session_transaction() as sess:
        assert "user_id" not in sess


# ------------------------------------------------------------------ #
# Page content                                                        #
# ------------------------------------------------------------------ #

def test_user_card(logged_in):
    body = get_profile_body(logged_in)
    assert NAV_NAME in body
    assert EMAIL in body
    assert ">AL<" in body
    # created_at is stored in UTC; allow for a month boundary.
    months = {datetime.now().strftime("%B %Y"),
              datetime.now(timezone.utc).strftime("%B %Y")}
    assert any(f"Member since {m}" in body for m in months)


def test_summary_stats(logged_in, with_expenses):
    body = get_profile_body(logged_in)
    assert "₹175.49" in body
    assert "Transactions" in body
    assert '<p class="profile-stat__value">4</p>' in body
    assert '<p class="profile-stat__value">Bills</p>' in body


def test_transaction_rows(logged_in, with_expenses):
    body = get_profile_body(logged_in)
    assert body.count('class="profile-table__row"') == len(SAMPLE_EXPENSES)
    # Newest first.
    assert body.index("20 Sep 2026") < body.index("17 Sep 2026") \
        < body.index("05 Sep 2026") < body.index("02 Sep 2026")
    assert "No expenses yet." not in body


def test_category_breakdown(logged_in, with_expenses):
    items = get_profile_body(logged_in).count('class="profile-breakdown__item"')
    assert items == 3


def test_zero_expenses_shows_empty_state(logged_in):
    body = get_profile_body(logged_in)
    assert "₹0.00" in body
    assert '<p class="profile-stat__value">0</p>' in body
    assert '<p class="profile-stat__value">—</p>' in body
    assert "No expenses yet." in body
    assert "No spending to break down yet." in body
    assert 'class="profile-table__row"' not in body
    assert 'class="profile-breakdown__item"' not in body


def test_other_users_expenses_are_not_shown(logged_in, with_expenses):
    other_id = db.create_user("Grace Hopper", "grace@example.com", "anotherpass1")
    add_expense(other_id, 5000.00, "Shopping", "2026-09-21", "Secret yacht")
    body = get_profile_body(logged_in)
    assert "Secret yacht" not in body
    assert "₹175.49" in body
    assert "profile-badge--shopping" not in body


def test_navbar_logged_in_state(logged_in):
    body = get_profile_body(logged_in)
    assert NAV_NAME in body
    assert "Sign out" in body
    assert "Get started" not in body


def test_badges_use_classes_not_inline_styles(logged_in, with_expenses):
    body = get_profile_body(logged_in)
    assert "profile-badge--food" in body
    assert "style=" not in body


def test_page_links_profile_stylesheet(logged_in):
    assert "css/profile.css" in get_profile_body(logged_in)


def test_app_module_contains_no_sql():
    source = (ROOT / "app.py").read_text()
    assert "get_db" not in source
    assert "execute" not in source
    assert "SELECT" not in source


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
    expenses = [
        {"category": "Food", "amount": 1850.00},
        {"category": "Other", "amount": 1100.00},
        {"category": "Entertainment", "amount": 450.00},
        {"category": "Shopping", "amount": 1500.00},
        {"category": "Health", "amount": 650.00},
        {"category": "Bills", "amount": 2200.00},
        {"category": "Transport", "amount": 800.00},
        {"category": "Food", "amount": 2450.00},
    ]
    summary = profile_mod.summarize_expenses(expenses)
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


# ------------------------------------------------------------------ #
# Row → template shaping                                             #
# ------------------------------------------------------------------ #

def test_build_profile_user(profile_mod):
    user = profile_mod.build_profile_user({
        "name": "Ada Lovelace", "email": EMAIL,
        "created_at": "2026-09-02 10:00:00",
    })
    assert user == {"name": "Ada Lovelace", "email": EMAIL,
                    "initials": "AL", "member_since": "September 2026"}


def test_build_profile_user_edge_cases(profile_mod):
    build = profile_mod.build_profile_user
    assert build({"name": "Cher", "email": "c@x.io",
                  "created_at": None})["initials"] == "C"
    assert build({"name": "Mary Ann Evans", "email": "m@x.io",
                  "created_at": None})["initials"] == "MA"
    assert build({"name": "", "email": "e@x.io",
                  "created_at": None})["initials"] == "?"
    assert build({"name": "Ada", "email": "a@x.io",
                  "created_at": None})["member_since"] == ""
    assert build({"name": "Ada", "email": "a@x.io",
                  "created_at": "garbage"})["member_since"] == "garbage"


def test_build_profile_expense(profile_mod):
    expense = profile_mod.build_profile_expense({
        "date": "2026-09-02", "description": None,
        "category": "Food", "amount": 45,
    })
    assert expense == {"date": "2026-09-02", "date_label": "02 Sep 2026",
                       "description": "", "category": "Food", "amount": 45.0}
    assert isinstance(expense["amount"], float)


# ------------------------------------------------------------------ #
# Date filter — parsing helpers                                       #
# ------------------------------------------------------------------ #

INVALID_DATE = "Invalid date — showing all expenses."
DATE_ORDER = "Start date must be on or before end date."
ROW = 'class="profile-table__row"'


def test_parse_date_filter_valid_range(profile_mod):
    assert profile_mod.parse_date_filter(
        {"start": "2026-09-01", "end": "2026-09-30"}
    ) == (date(2026, 9, 1), date(2026, 9, 30), None)


def test_parse_date_filter_open_ranges(profile_mod):
    parse = profile_mod.parse_date_filter
    assert parse({"start": "2026-09-01"}) == (date(2026, 9, 1), None, None)
    assert parse({"end": "2026-09-30"}) == (None, date(2026, 9, 30), None)


def test_parse_date_filter_missing_or_empty(profile_mod):
    parse = profile_mod.parse_date_filter
    assert parse({}) == (None, None, None)
    assert parse({"start": "", "end": ""}) == (None, None, None)


@pytest.mark.parametrize("value", ["abc", "2026-02-30", "20260902",
                                   "2026-9-1", "2026-13-01"])
def test_parse_date_filter_invalid(profile_mod, value):
    assert profile_mod.parse_date_filter({"start": value}) == \
        (None, None, INVALID_DATE)


def test_parse_date_filter_invalid_drops_both_bounds(profile_mod):
    assert profile_mod.parse_date_filter(
        {"start": "2026-09-01", "end": "abc"}
    ) == (None, None, INVALID_DATE)


def test_parse_date_filter_start_after_end(profile_mod):
    assert profile_mod.parse_date_filter(
        {"start": "2026-09-20", "end": "2026-09-01"}
    ) == (None, None, DATE_ORDER)


def test_parse_date_filter_same_day(profile_mod):
    assert profile_mod.parse_date_filter(
        {"start": "2026-09-05", "end": "2026-09-05"}
    ) == (date(2026, 9, 5), date(2026, 9, 5), None)


def test_build_date_presets_mid_month(profile_mod):
    assert profile_mod.build_date_presets(date(2026, 9, 25)) == [
        {"label": "This month", "start": "2026-09-01", "end": "2026-09-25"},
        {"label": "Last 30 days", "start": "2026-08-27", "end": "2026-09-25"},
        {"label": "All time", "start": None, "end": None},
    ]


def test_build_date_presets_month_boundary(profile_mod):
    this_month, last_30, _ = profile_mod.build_date_presets(date(2026, 3, 1))
    assert (this_month["start"], this_month["end"]) == \
        ("2026-03-01", "2026-03-01")
    assert (last_30["start"], last_30["end"]) == ("2026-01-31", "2026-03-01")


def test_build_date_filter_labels(profile_mod):
    build = profile_mod.build_date_filter
    both = build(date(2026, 9, 5), date(2026, 9, 17), None)
    assert both == {"start": "2026-09-05", "end": "2026-09-17",
                    "error": None, "active": True,
                    "label": "Showing 05 Sep 2026 – 17 Sep 2026"}
    assert build(date(2026, 9, 5), None, None)["label"] == "From 05 Sep 2026"
    assert build(None, date(2026, 9, 17), None)["label"] == "Up to 17 Sep 2026"
    none = build(None, None, INVALID_DATE)
    assert none["active"] is False and none["label"] is None
    assert none["error"] == INVALID_DATE


# ------------------------------------------------------------------ #
# Date filter — database helper                                       #
# ------------------------------------------------------------------ #

def test_get_expenses_by_user_date_bounds(user_id, with_expenses):
    rows = db.get_expenses_by_user(user_id, "2026-09-05", "2026-09-17")
    assert [r["date"] for r in rows] == ["2026-09-17", "2026-09-05"]
    assert len(db.get_expenses_by_user(user_id)) == len(SAMPLE_EXPENSES)
    assert len(db.get_expenses_by_user(user_id, start_date="2026-09-17")) == 2
    assert len(db.get_expenses_by_user(user_id, end_date="2026-09-04")) == 1


# ------------------------------------------------------------------ #
# Date filter — /profile route                                        #
# ------------------------------------------------------------------ #

def test_filter_inclusive_both_bounds(logged_in, with_expenses):
    body = get_profile_body(logged_in, start="2026-09-05", end="2026-09-17")
    assert body.count(ROW) == 2
    assert "Electricity bill" in body
    assert "Restaurant dinner" in body
    assert "Groceries" not in body
    assert "₹119.99" in body
    assert '<p class="profile-stat__value">2</p>' in body


def test_filter_only_start(logged_in, with_expenses):
    body = get_profile_body(logged_in, start="2026-09-17")
    assert body.count(ROW) == 2
    assert "₹40.00" in body
    assert '<p class="profile-stat__value">Food</p>' in body
    assert "From 17 Sep 2026" in body


def test_filter_only_end(logged_in, with_expenses):
    body = get_profile_body(logged_in, end="2026-09-05")
    assert body.count(ROW) == 2
    assert "₹135.49" in body
    assert '<p class="profile-stat__value">Bills</p>' in body
    assert "Up to 05 Sep 2026" in body


def test_filter_recomputes_breakdown(logged_in, with_expenses):
    body = get_profile_body(logged_in, start="2026-09-17", end="2026-09-20")
    assert body.count('class="profile-breakdown__item"') == 2
    assert "profile-badge--bills" not in body


def test_filter_no_matches_shows_period_empty_state(logged_in, with_expenses):
    body = get_profile_body(logged_in, start="2027-01-01")
    assert "₹0.00" in body
    assert '<p class="profile-stat__value">0</p>' in body
    assert '<p class="profile-stat__value">—</p>' in body
    assert "No expenses in this period." in body
    assert "No expenses yet." not in body


def test_filter_prefills_inputs_and_caption(logged_in, with_expenses):
    body = get_profile_body(logged_in, start="2026-09-05", end="2026-09-17")
    assert 'value="2026-09-05"' in body
    assert 'value="2026-09-17"' in body
    assert "Showing 05 Sep 2026 – 17 Sep 2026" in body


def test_filter_excludes_other_users_in_range(logged_in, with_expenses):
    other_id = db.create_user("Grace Hopper", "grace@example.com",
                              "anotherpass1")
    add_expense(other_id, 5000.00, "Shopping", "2026-09-10", "Secret yacht")
    body = get_profile_body(logged_in, start="2026-09-01", end="2026-09-30")
    assert "Secret yacht" not in body
    assert "₹175.49" in body


@pytest.mark.parametrize("value", ["abc", "2026-02-30"])
def test_invalid_date_shows_error_and_all_expenses(logged_in, with_expenses,
                                                   value):
    body = get_profile_body(logged_in, start=value)
    assert INVALID_DATE in body
    assert 'role="alert"' in body
    assert body.count(ROW) == len(SAMPLE_EXPENSES)
    assert "₹175.49" in body


def test_start_after_end_shows_error_and_all_expenses(logged_in,
                                                      with_expenses):
    body = get_profile_body(logged_in, start="2026-09-20", end="2026-09-01")
    assert DATE_ORDER in body
    assert body.count(ROW) == len(SAMPLE_EXPENSES)
    assert 'value="2026-09-20"' not in body


def test_no_params_shows_all_and_all_time_active(logged_in, with_expenses):
    body = get_profile_body(logged_in)
    assert body.count(ROW) == len(SAMPLE_EXPENSES)
    assert 'role="alert"' not in body
    assert "profile-filter__caption" not in body
    assert re.search(r'is-active"\s+aria-current="true">All time<', body)
    assert body.count("is-active") == 1


def test_this_month_preset_is_active(logged_in, profile_mod):
    preset = profile_mod.build_date_presets(date.today())[0]
    body = get_profile_body(logged_in, start=preset["start"],
                            end=preset["end"])
    assert re.search(r'is-active"\s+aria-current="true">This month<', body)
    assert body.count("is-active") == 1


def test_filter_bar_markup(logged_in):
    body = get_profile_body(logged_in)
    assert 'method="get"' in body
    assert 'action="/profile"' in body
    assert 'type="date"' in body
    assert 'name="start"' in body and 'name="end"' in body
    for text in ("Apply", "Clear", "This month", "Last 30 days", "All time"):
        assert text in body
    assert "style=" not in body


def test_filtered_profile_redirects_when_logged_out(client):
    resp = client.get("/profile?start=2026-09-01")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"


def test_clear_and_all_time_link_to_unfiltered_profile(logged_in,
                                                       with_expenses):
    body = get_profile_body(logged_in, start="2026-09-05", end="2026-09-17")
    assert re.search(r'href="/profile"\s+class="btn-ghost">Clear<', body)
    assert re.search(
        r'href="/profile"\s+class="profile-filter__preset">All time<', body)
    # Following either link lands on the unfiltered view.
    body = get_profile_body(logged_in)
    assert body.count(ROW) == len(SAMPLE_EXPENSES)
    assert "profile-filter__caption" not in body


def test_demo_user_unfiltered_totals(client, app):
    # seed_db() only seeds an empty DB, so this is safe whichever test
    # happened to import `app` (and seed) first.
    db.seed_db()
    client.post("/login", data={"email": "demo@spendly.com",
                                "password": "demo123"})
    body = get_profile_body(client)
    assert "₹288.24" in body
    assert '<p class="profile-stat__value">8</p>' in body
    assert body.count(ROW) == 8
