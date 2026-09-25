import os
import re
from datetime import date, datetime, timedelta

from flask import (Flask, flash, redirect, render_template, request,
                   session, url_for)

from database.db import (CATEGORIES, authenticate_user, create_user,
                         get_expenses_by_user, get_user_by_email,
                         get_user_by_id, init_db, seed_db)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

with app.app_context():
    init_db()
    seed_db()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DUPLICATE_EMAIL_ERROR = "An account with that email already exists."
LOGIN_ERROR = "Invalid email or password."
INVALID_DATE_ERROR = "Invalid date — showing all expenses."
DATE_ORDER_ERROR = "Start date must be on or before end date."


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def validate_registration(name, email, password):
    if not name or len(name) > 100:
        return "Please enter your name."
    if not EMAIL_RE.match(email):
        return "Please enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    return None


def _initials(name):
    words = (name or "").split()
    return "".join(word[0] for word in words[:2]).upper() or "?"


def _format_date(value, fmt):
    try:
        return datetime.fromisoformat(value).strftime(fmt)
    except (TypeError, ValueError):
        return value or ""


def build_profile_user(row):
    return {
        "name": row["name"],
        "email": row["email"],
        "initials": _initials(row["name"]),
        "member_since": _format_date(row["created_at"], "%B %Y"),
    }


def build_profile_expense(row):
    return {
        "date": row["date"],
        "date_label": _format_date(row["date"], "%d %b %Y"),
        "description": (row["description"] or "").strip(),
        "category": row["category"],
        "amount": float(row["amount"]),
    }


def summarize_expenses(expenses):
    amounts = {}
    for expense in expenses:
        name = expense["category"]
        amounts[name] = amounts.get(name, 0) + expense["amount"]

    total = round(sum(amounts.values()), 2)
    categories = []
    for name, amount in sorted(amounts.items(), key=lambda item: item[1],
                               reverse=True):
        share = amount / total if total else 0
        categories.append({
            "name": name,
            "slug": name.lower() if name in CATEGORIES else "other",
            "amount": amount,
            "percent": round(share * 100),
            "bar_step": max(5, min(100, 5 * round(share * 20))),
        })

    return {
        "total": total,
        "count": len(expenses),
        "top_category": categories[0] if categories else None,
        "categories": categories,
    }


def _parse_iso_date(value):
    """Return (date or None, ok). A missing or empty value is ok."""
    value = (value or "").strip()
    if not value:
        return None, True
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None, False
    # fromisoformat also accepts forms like "20260902"; require YYYY-MM-DD.
    if parsed.isoformat() != value:
        return None, False
    return parsed, True


def parse_date_filter(args):
    start, start_ok = _parse_iso_date(args.get("start"))
    end, end_ok = _parse_iso_date(args.get("end"))
    if not (start_ok and end_ok):
        return None, None, INVALID_DATE_ERROR
    if start and end and start > end:
        return None, None, DATE_ORDER_ERROR
    return start, end, None


def build_date_presets(today):
    today_iso = today.isoformat()
    return [
        {"label": "This month",
         "start": today.replace(day=1).isoformat(), "end": today_iso},
        {"label": "Last 30 days",
         "start": (today - timedelta(days=29)).isoformat(), "end": today_iso},
        {"label": "All time", "start": None, "end": None},
    ]


def build_date_filter(start, end, error):
    start_iso = start.isoformat() if start else None
    end_iso = end.isoformat() if end else None
    start_label = _format_date(start_iso, "%d %b %Y")
    end_label = _format_date(end_iso, "%d %b %Y")

    if start_iso and end_iso:
        label = f"Showing {start_label} – {end_label}"
    elif start_iso:
        label = f"From {start_label}"
    elif end_iso:
        label = f"Up to {end_label}"
    else:
        label = None

    return {
        "start": start_iso,
        "end": end_iso,
        "error": error,
        "active": label is not None,
        "label": label,
    }


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = validate_registration(name, email, password)
    if error is None and get_user_by_email(email) is not None:
        error = DUPLICATE_EMAIL_ERROR
    if error is None and create_user(name, email, password) is None:
        error = DUPLICATE_EMAIL_ERROR
    if error:
        return render_template("register.html", error=error,
                               name=name, email=email), 400

    flash("Account created — please sign in.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = authenticate_user(email, password) if email and password else None
    if user is None:
        return render_template("login.html", error=LOGIN_ERROR,
                               email=email), 401

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.")
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user_row = get_user_by_id(user_id)
    if user_row is None:
        session.clear()
        return redirect(url_for("login"))

    date_filter = build_date_filter(*parse_date_filter(request.args))
    rows = get_expenses_by_user(user_id, date_filter["start"],
                                date_filter["end"])
    expenses = [build_profile_expense(row) for row in rows]
    return render_template("profile.html", user=build_profile_user(user_row),
                           expenses=expenses,
                           summary=summarize_expenses(expenses),
                           filter=date_filter,
                           presets=build_date_presets(date.today()))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
