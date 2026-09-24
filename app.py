import os
import re

from flask import (Flask, flash, redirect, render_template, request,
                   session, url_for)

from database.db import (CATEGORIES, authenticate_user, create_user,
                         get_user_by_email, init_db, seed_db)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

with app.app_context():
    init_db()
    seed_db()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DUPLICATE_EMAIL_ERROR = "An account with that email already exists."
LOGIN_ERROR = "Invalid email or password."

# Hardcoded profile data for Step 4 — replaced by real queries in Step 5.
PROFILE_USER = {"name": "Demo User", "email": "demo@spendly.com",
                "initials": "DU", "member_since": "January 2026"}
PROFILE_EXPENSES = [  # newest first; amounts in rupees
    {"date": "2026-09-18", "date_label": "18 Sep 2026", "description": "Restaurant dinner",
     "category": "Food", "amount": 1850.00},
    {"date": "2026-09-15", "date_label": "15 Sep 2026", "description": "Birthday gift",
     "category": "Other", "amount": 1100.00},
    {"date": "2026-09-12", "date_label": "12 Sep 2026", "description": "Movie tickets",
     "category": "Entertainment", "amount": 450.00},
    {"date": "2026-09-10", "date_label": "10 Sep 2026", "description": "Running shoes",
     "category": "Shopping", "amount": 1500.00},
    {"date": "2026-09-08", "date_label": "08 Sep 2026", "description": "Pharmacy",
     "category": "Health", "amount": 650.00},
    {"date": "2026-09-05", "date_label": "05 Sep 2026", "description": "Electricity bill",
     "category": "Bills", "amount": 2200.00},
    {"date": "2026-09-04", "date_label": "04 Sep 2026", "description": "Metro card top-up",
     "category": "Transport", "amount": 800.00},
    {"date": "2026-09-02", "date_label": "02 Sep 2026", "description": "Groceries",
     "category": "Food", "amount": 2450.00},
]


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
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("profile.html", user=PROFILE_USER,
                           expenses=PROFILE_EXPENSES,
                           summary=summarize_expenses(PROFILE_EXPENSES))


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
