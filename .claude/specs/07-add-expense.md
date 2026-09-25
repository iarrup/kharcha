# Spec: Add Expense

## Overview
Steps 5 and 6 let a logged-in user view and filter their expenses on `/profile`, but the only data comes from the seed script. There's no way to record a new expense yet. This step replaces the `/expenses/add` stub with a real feature. `GET /expenses/add` shows a form with amount, category, date and an optional description. `POST /expenses/add` validates the input on the server, inserts the row for the logged-in user through a new helper in `database/db.py`, flashes a confirmation and redirects to `/profile`, where the new expense shows in the table, the stats and the category breakdown. If validation fails, the form is shown again with an inline error and the values the user entered. The profile page gets an "Add expense" link so the feature can be found. Edit (Step 8) and delete (Step 9) stay stubs.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()` with `PRAGMA foreign_keys = ON`, `CATEGORIES`)
- Step 3: Login + Logout (`session["user_id"]`)
- Step 4: Profile page design (`templates/profile.html`, `static/css/profile.css`)
- Step 5: Backend routes for profile page (`get_expenses_by_user()` shows the new row)
- Step 6: Date filter on profile page (`_parse_iso_date()` can be reused for date validation)

## Routes
- `GET /expenses/add` — render the add-expense form. The date defaults to today and no category is selected — logged-in
- `POST /expenses/add` — validate the form, insert the expense for `session["user_id"]`, flash "Expense added.", and redirect to `url_for('profile')` — logged-in
  - Not logged in (GET or POST) → redirect to `/login`. Nothing is inserted
  - Validation failure → re-render `add_expense.html` with status **400**, an inline error message and the submitted values kept in the form

Both methods use the existing `add_expense` endpoint name, so `url_for('add_expense')` keeps working. The decorator becomes `@app.route("/expenses/add", methods=["GET", "POST"])`.

## Database changes
No database changes. The `expenses` table already has `user_id`, `amount`, `category`, `date`, `description` and `created_at`.

New helper in `database/db.py` (no schema change):
- `create_expense(user_id, amount, category, date, description)` → returns the new row's `id`
  - `INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)`
  - Uses `get_db()`, commits, and closes the connection in `finally`, in the same style as `create_user()`
  - `description` may be `None`. Store `None` rather than an empty string when it is blank

## Templates
- **Create:** `templates/add_expense.html`
  - Extends `base.html`. Title block: "Add expense — Spendly"
  - Loads `static/css/expense.css` in the `head` block
  - `<form method="post" action="{{ url_for('add_expense') }}">` with a `<label>` for every field:
    - Amount: `<input type="number" name="amount" step="0.01" min="0.01" required>`
    - Category: `<select name="category" required>` with a disabled placeholder option ("Choose a category") and one option per entry in `categories` (passed from the route, sourced from `CATEGORIES`). The submitted value is pre-selected when the form is re-rendered
    - Date: `<input type="date" name="date" required>`, defaulting to today's ISO date
    - Description: `<input type="text" name="description" maxlength="200">`, optional
  - Inline error block (`role="alert"`) shown when `error` is set
  - Submit button "Add expense" and a "Cancel" link to `url_for('profile')`
  - Reuse the existing `.form-group`, `.form-input`, `.btn-primary`/`.btn-submit`, `.btn-ghost` and `.auth-error` classes where they fit
- **Modify:** `templates/profile.html`
  - Add an "Add expense" link (`url_for('add_expense')`, styled with `.btn-primary`) in the profile header or next to the "Recent transactions" heading. Keep all existing class names and markup

## Files to change
- `app.py`
  - Import `create_expense` from `database.db`
  - Add a pure helper `validate_expense(form)` with no DB access. It returns `(data, error)`, where `data` is `{amount, category, date, description}` with cleaned values and `error` is a message string or `None`. Rules, checked in this order:
    - Amount: required, parses as a finite float (`math.isfinite`), `> 0`, `<= 10,000,000`. Round to 2 decimal places. Error: "Please enter an amount greater than 0."
    - Category: must be exactly one of `CATEGORIES`. Error: "Please choose a valid category."
    - Date: required, strict `YYYY-MM-DD` (reuse `_parse_iso_date()`), not in the future (`<= date.today()`). Errors: "Please enter a valid date." / "Date can't be in the future."
    - Description: strip it. Empty becomes `None`. Longer than 200 characters → "Description must be 200 characters or fewer."
  - Replace the `add_expense()` stub. It redirects when not logged in, renders the form on GET, and on POST runs validate → `create_expense()` → flash → redirect, or re-renders with 400. The route stays thin, with no SQL
- `templates/profile.html` — the "Add expense" link described above
- `CLAUDE.md` — mark `GET/POST /expenses/add` as "Implemented (Step 7)" in the routes table

## Files to create
- `templates/add_expense.html` — the add-expense form page
- `static/css/expense.css` — styles for the add-expense page (form card, layout, select styling to match `.form-input`, action row). It uses existing CSS variables only. The file is named generically so Step 8's edit form can reuse it
- `tests/test_add_expense.py` — tests for the helper, the validator and the routes (see Definition of done)

## New dependencies
No new dependencies. Use the standard library `math` and `datetime`.

## Rules for implementation
- No SQLAlchemy or ORMs. Use raw `sqlite3` through `get_db()` only
- Parameterised queries only (`?` placeholders). Never use f-strings, `%` or `.format()` in SQL
- Passwords hashed with werkzeug (auth code is not touched in this step)
- Use CSS variables. Never hardcode hex values
- All templates extend `base.html`
- All SQL lives in `database/db.py`. `app.py` must not call `get_db()` or `conn.execute`
- The expense's `user_id` always comes from `session["user_id"]`. Never read a user ID from the form or query string
- Validate everything on the server. HTML `required`/`min` attributes are only a convenience
- Category is checked against the `CATEGORIES` list. Never trust a free-text category
- Invalid input never produces a 500. Re-render the form with a friendly error and status 400
- Every link and form action uses `url_for()`
- No inline `<style>` or `style=""` attributes. Page styles go in `expense.css`
- No JavaScript is required. The form works as a plain POST
- Use `abort()` for HTTP errors, never bare error strings
- Do not implement or touch the Step 8 (edit) and Step 9 (delete) stub routes
- App still runs on port 5001

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`. POSTing while logged out also redirects and inserts nothing
- [ ] Visiting `/expenses/add` while logged in shows a form with Amount, Category (all 7 categories), Date (pre-filled with today) and Description fields, an "Add expense" button and a "Cancel" link back to `/profile`
- [ ] The profile page has an "Add expense" link that opens the form
- [ ] Submitting a valid expense (e.g. 250.00, Food, today, "Lunch") redirects to `/profile`, shows the "Expense added." flash, and the new row appears at the top of the transactions table
- [ ] Total spent, Transactions and Spending by category on `/profile` include the new expense (demo user: ₹288.24 → ₹538.24, 8 → 9 transactions)
- [ ] Submitting with no description succeeds, and the row is stored with a NULL description
- [ ] Amount `0`, `-5`, `abc`, `nan`, `inf` or blank returns 400 with "Please enter an amount greater than 0." and nothing is inserted
- [ ] A category not in the list (e.g. `Crypto`), or a blank one, returns 400 with "Please choose a valid category."
- [ ] Date `2026-02-30`, `abc` or blank returns 400 with "Please enter a valid date." A future date returns 400 with "Date can't be in the future."
- [ ] A description longer than 200 characters returns 400 with the length error
- [ ] After a validation error, the form keeps the previously entered amount, category, date and description
- [ ] The new expense belongs to the logged-in user only. Another logged-in user doesn't see it on their profile
- [ ] A `user_id` field injected into the POST body is ignored
- [ ] `app.py` contains no SQL, and `create_expense()` uses only `?` placeholders
- [ ] No hex colour values or inline styles in `add_expense.html` or `expense.css`
- [ ] The edit and delete stub routes are unchanged
- [ ] `pytest` passes
