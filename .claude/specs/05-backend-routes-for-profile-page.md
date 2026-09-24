# Spec: Backend Routes For Profile Page

## Overview
Step 4 built the complete `/profile` UI against hardcoded Python data (`PROFILE_USER` and `PROFILE_EXPENSES` in `app.py`). This step connects that page to the database: the user card shows the logged-in user's real name, email and join date from the `users` table, and the summary stats, transaction table and category breakdown are computed from that user's rows in the `expenses` table. The template layout and styling stay as they are. Only the data source changes, plus an empty state for users with no expenses. With this step done, `/profile` is ready for the add, edit and delete flows in Steps 7–9.

## Depends on
- Step 1: Database setup (`users` and `expenses` tables, `get_db()` with `PRAGMA foreign_keys = ON`, seed data)
- Step 2: Registration (real user rows exist)
- Step 3: Login + Logout (`session["user_id"]` is set on login)
- Step 4: Profile page design (`templates/profile.html`, `static/css/profile.css`, `summarize_expenses()`)

## Routes
No new routes. The existing route changes behaviour:
- `GET /profile` — render the profile page from the database for `session["user_id"]` — logged-in
  - Not logged in → redirect to `/login` (unchanged)
  - `session["user_id"]` refers to a user that no longer exists → `session.clear()` and redirect to `/login`

## Database changes
No database changes. The existing `users` (`id`, `name`, `email`, `created_at`) and `expenses` (`user_id`, `amount`, `category`, `date`, `description`) columns cover everything the page needs.

New read helpers in `database/db.py` (no schema changes):
- `get_user_by_id(user_id)` returns the `users` row or `None`
- `get_expenses_by_user(user_id)` returns a list of that user's expense rows ordered `date DESC, id DESC`

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Change the header subtitle from "this month's spending" to wording that matches all-time data, e.g. "Your account details and a summary of your spending."
  - Transactions table: when `expenses` is empty, render a single empty-state row, e.g. "No expenses yet.", instead of an empty `<tbody>`
  - Category breakdown: when `summary.categories` is empty, render an empty-state message instead of an empty `<ul>`
  - Keep all existing class names, `url_for()` usage and the `profile.css` link

## Files to change
- `database/db.py` — add `get_user_by_id()` and `get_expenses_by_user()`, both using `get_db()`, parameterised queries and `try/finally: conn.close()` like the existing helpers
- `app.py`
  - Remove `PROFILE_USER`, `PROFILE_EXPENSES` and the "Hardcoded profile data" comment
  - Import the two new DB helpers
  - Add pure helpers, with no DB access, that turn DB rows into the dict shapes the template already expects:
    - `build_profile_user(row)` returns `{name, email, initials, member_since}`. `initials` is the first letter of the first two words of the name, uppercased (fall back to one letter). `member_since` is `created_at` formatted as `"%B %Y"`, e.g. "September 2026"
    - `build_profile_expense(row)` returns `{date, date_label, description, category, amount}`. `date_label` is `"%d %b %Y"`, e.g. "02 Sep 2026". A missing description falls back to `""` or the category name
  - Rewrite `profile()`: guard the session, fetch the user (clear the session and redirect if missing), fetch the expenses, map them through the helpers, call `summarize_expenses()` and render. No SQL in the route
- `templates/profile.html` — the empty states and subtitle described above
- `tests/test_profile.py` — replace the Step-4 hardcoded-data assertions:
  - Remove `test_profile_route_makes_no_db_calls` and assertions tied to `PROFILE_*`, e.g. `₹11,000.00`
  - Add tests that log in as a registered user and insert expenses through `get_db()` in the test DB. Then check that the page shows that user's name and email, the correct total, count and top category, rows newest first, and categories from the breakdown
  - Add a test that another user's expenses never appear (data isolation)
  - Add a test for a user with zero expenses: page returns 200, shows ₹0.00, 0 transactions and the empty-state text
  - Add a test that a stale `session["user_id"]` for a user that doesn't exist redirects to `/login` and clears the session
  - Keep the existing unit tests for `summarize_expenses()` and add unit tests for `build_profile_user()` and `build_profile_expense()`

## Files to create
None. All changes go into existing files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs. Use raw `sqlite3` through `get_db()` only
- Parameterised queries only (`?` placeholders). Never use f-strings or `%` in SQL
- Passwords hashed with werkzeug (auth code is not touched in this step)
- Use CSS variables. Never hardcode hex values
- All templates extend `base.html`
- All SQL lives in `database/db.py`. `app.py` must not call `get_db()` or `conn.execute` directly
- Every expense query is scoped with `WHERE user_id = ?` using `session["user_id"]`. Never trust an ID from the request for this page
- The route stays a thin "fetch → shape → render" function. Formatting belongs in the helper functions
- Reuse `summarize_expenses()` unchanged. Don't duplicate its aggregation in SQL
- No inline `<style>` or `style=""` attributes. Category badges keep using `profile-badge--<slug>` classes
- Do not implement or touch the Step 7–9 stub routes (`/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`)
- App still runs on port 5001

## Definition of done
- [ ] `PROFILE_USER` and `PROFILE_EXPENSES` no longer exist in `app.py`
- [ ] Visiting `/profile` logged out redirects to `/login`
- [ ] Logging in as `demo@spendly.com` / `demo123` and visiting `/profile` shows "Demo User", `demo@spendly.com` and initials "DU"
- [ ] "Member since" shows the month and year of the demo user's `created_at`, not the hardcoded "January 2026"
- [ ] The demo user's page shows the 8 seeded expenses, newest date first, with the matching dates, descriptions, category badges and amounts
- [ ] The Total spent stat equals the sum of the demo user's seeded amounts (₹288.24) and Transactions shows 8
- [ ] Top category is Bills (₹89.99), and the breakdown lists all 7 categories sorted by amount with percentages
- [ ] Registering a new account, logging in and visiting `/profile` shows that user's name and email, ₹0.00, 0 transactions, "—" for top category and the empty-state messages, with no errors
- [ ] Expenses belonging to one user never appear on another user's profile
- [ ] Deleting the logged-in user's row, then reloading `/profile`, redirects to `/login` instead of erroring
- [ ] `app.py` contains no SQL, and both new DB helpers use `?` placeholders
- [ ] No hex colour values in `profile.html` or `profile.css`
- [ ] `pytest` passes
