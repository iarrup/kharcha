# Spec: Date Filter Profile Page

## Overview
Step 5 connected `/profile` to the database, so the page now shows every expense the logged-in user has ever recorded. This step adds a date-range filter so the user can narrow the page to a period, for example this month or a custom range. The filter uses optional `start` and `end` query-string parameters on the existing `GET /profile` route. The summary stats (total, transaction count, top category), the transactions table and the category breakdown all reflect only the expenses inside the selected range. A small filter bar above the stats has two date inputs, an Apply button, a Clear link and quick presets ("This month", "Last 30 days", "All time"). Filtering is done in SQL through `database/db.py`, and the page keeps working with no parameters, where it shows all expenses as it does today.

## Depends on
- Step 1: Database setup (`expenses.date` stored as `YYYY-MM-DD` text, `get_db()`)
- Step 3: Login + Logout (`session["user_id"]`)
- Step 4: Profile page design (`templates/profile.html`, `static/css/profile.css`, `summarize_expenses()`)
- Step 5: Backend routes for profile page (`get_expenses_by_user()`, `build_profile_expense()`, empty states)

## Routes
No new routes. The existing route gains optional query parameters:
- `GET /profile?start=YYYY-MM-DD&end=YYYY-MM-DD` — render the profile page filtered to expenses with `start <= date <= end` (both bounds inclusive) — logged-in
  - Either parameter may be omitted or empty. A missing `start` means no lower bound, and a missing `end` means no upper bound
  - No parameters → all expenses (current behaviour, unchanged)
  - A value that isn't a valid ISO date, e.g. `start=abc` or `end=2026-02-30`, is ignored (treated as absent) and an inline error message is shown: "Invalid date — showing all expenses." The page still returns 200
  - `start` later than `end` → no filter is applied, an inline error is shown ("Start date must be on or before end date."), and the page returns 200
  - Not logged in → redirect to `/login` (unchanged)

## Database changes
No database changes. `expenses.date` is already stored as ISO `YYYY-MM-DD` text, so lexical comparison in SQLite is correct.

Helper change in `database/db.py` (no schema change):
- Extend `get_expenses_by_user(user_id, start_date=None, end_date=None)`
  - Always `WHERE user_id = ?`
  - Append `AND date >= ?` only when `start_date` is given, and `AND date <= ?` only when `end_date` is given
  - Bind the values through a params tuple/list. Build the SQL only from fixed string fragments, never by interpolating user values
  - Keep `ORDER BY date DESC, id DESC`
  - Existing callers that pass only `user_id` keep working unchanged

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter bar (`<form method="get" action="{{ url_for('profile') }}" class="profile-filter">`) between the user card and the stats section containing:
    - `<input type="date" name="start">` and `<input type="date" name="end">` with `<label>`s, pre-filled with the currently applied values
    - An "Apply" submit button
    - A "Clear" link to `url_for('profile')`
    - Preset links built with `url_for('profile', start=..., end=...)`: "This month", "Last 30 days", "All time". The active preset gets an `is-active` / `aria-current="true"` marker
  - Show the inline error message (if any) in the filter bar with `role="alert"`
  - When a filter is active, show a short caption such as "Showing 01 Sep 2026 – 25 Sep 2026" (or "From …" / "Up to …" for open ranges)
  - Rename the "Recent transactions" heading only if needed for clarity. Keep all existing class names
  - Change the empty-state text to "No expenses in this period." when a filter is active, and keep "No expenses yet." otherwise

## Files to change
- `database/db.py` — add optional `start_date` / `end_date` params to `get_expenses_by_user()` as described above
- `app.py`
  - Add a pure helper `parse_date_filter(args)` with no DB access. It reads `start` / `end` from `request.args`, validates them with `date.fromisoformat()`, and returns `(start_date, end_date, error)`. Invalid values become `None`. If `start > end`, it returns `(None, None, error)`
  - Add a pure helper `build_date_presets(today)` that returns a list of `{label, start, end}` dicts for "This month" (1st of the current month → today), "Last 30 days" (today − 29 days → today) and "All time" (`None`, `None`). `today` is passed in so tests can stub it
  - Update `profile()` to call `parse_date_filter(request.args)`, pass the dates to `get_expenses_by_user()`, and pass `filter` (`{start, end, error, active, label}`) and `presets` to the template. The route stays thin: parse → fetch → shape → render
- `templates/profile.html` — the filter bar, caption, error and empty-state text described above
- `static/css/profile.css` — styles for `.profile-filter`, its inputs, buttons, preset pills, the active preset and the error message, using existing CSS variables only
- `tests/test_profile.py` — add tests (see Definition of done):
  - Unit tests for `parse_date_filter()`: valid range, only start, only end, empty strings, invalid format, impossible date (`2026-02-30`), start after end
  - Unit tests for `build_date_presets()` with a fixed `today`, including a month-boundary case
  - Route tests: an inclusive range on both boundaries, open-ended ranges, totals, counts and top category recomputed for the filtered set, another user's expenses excluded even when they fall inside the range, invalid params return 200 with the error text, and no params keeps showing all expenses

## Files to create
None. All changes go into existing files.

## New dependencies
No new dependencies. Use the standard library `datetime.date` / `timedelta`.

## Rules for implementation
- No SQLAlchemy or ORMs. Use raw `sqlite3` through `get_db()` only
- Parameterised queries only (`?` placeholders). Never use f-strings, `%` or `.format()` with user values in SQL. Dynamic `WHERE` fragments must be fixed literals
- Passwords hashed with werkzeug (auth code is not touched in this step)
- Use CSS variables. Never hardcode hex values
- All templates extend `base.html`
- All SQL lives in `database/db.py`. `app.py` must not call `get_db()` or `conn.execute` directly
- Every expense query stays scoped with `WHERE user_id = ?` from `session["user_id"]`. Never accept a user ID from the query string
- Validate dates server-side with `date.fromisoformat()`. Never pass raw request strings to the DB helper
- Invalid input never produces a 500. Show a friendly inline error and fall back to no filter
- Reuse `summarize_expenses()` and `build_profile_expense()` unchanged
- Every link and form action uses `url_for()`. No hardcoded `/profile?...` URLs
- No inline `<style>` or `style=""` attributes. Page-specific styles go in `profile.css`
- The filter works without JavaScript (plain GET form). Don't add JS unless it's a purely optional enhancement in `static/js/main.js`
- Do not implement or touch the Step 7–9 stub routes
- App still runs on port 5001

## Definition of done
- [ ] Visiting `/profile` with no query string shows all of the user's expenses and the same totals as before this step (demo user: ₹288.24, 8 transactions)
- [ ] The filter bar shows start/end date inputs, Apply, Clear, and the "This month", "Last 30 days" and "All time" presets
- [ ] Choosing a start and end date and clicking Apply reloads `/profile?start=…&end=…` and shows only expenses within that range, including expenses dated exactly on the start and end dates
- [ ] Total spent, Transactions, Top category and Spending by category all update to match the filtered expenses
- [ ] The date inputs stay pre-filled with the applied range after reload
- [ ] Supplying only `start` shows expenses on or after that date, and supplying only `end` shows expenses on or before it
- [ ] The "This month" preset shows only current-month expenses and is visibly marked active
- [ ] "Clear" and "All time" return to the unfiltered view
- [ ] A range with no matching expenses shows ₹0.00, 0 transactions, "—" for top category and "No expenses in this period."
- [ ] `/profile?start=abc` and `/profile?start=2026-02-30` return 200 with the "Invalid date" message and show all expenses
- [ ] `/profile?start=2026-09-20&end=2026-09-01` returns 200 with the "Start date must be on or before end date." message and no filter applied
- [ ] Another user's expenses never appear, even when their dates fall inside the selected range
- [ ] Visiting `/profile?start=…` while logged out redirects to `/login`
- [ ] `app.py` contains no SQL, and `get_expenses_by_user()` uses only `?` placeholders for the date bounds
- [ ] No hex colour values or inline styles added to `profile.html` or `profile.css`
- [ ] `pytest` passes
