## 1. Overview

Make the registration form at `/register` work end to end.

`GET /register` already renders the form, but submitting it does nothing. This step adds `POST /register`, which does the following:

- validates the input
- creates a user with a hashed password
- redirects to the login page with a success message

This step does **not** log the user in or create a session. Login and logout are Step 3.

---

## 2. Depends on

- Step 1: Database setup (`get_db()`, `init_db()` and the `users` table in `database/db.py`)

---

## 3. Routes

| Route | Change |
| --- | --- |
| `GET /register` | Unchanged: renders `register.html` |
| `POST /register` | **New.** Validates the input and creates the user, then redirects to `login` |

- Implement both methods in the existing `register()` view using `methods=["GET", "POST"]`
- Leave all other routes unchanged. Do not touch the `/logout`, `/profile` or expense stubs

---

## 4. Database Schema

- No schema changes. The existing `users` table is used as is:

| Column | Type | Constraints |
| --- | --- | --- |
| id | INTEGER | Primary key, autoincrement |
| name | TEXT | Not null |
| email | TEXT | Unique, not null |
| password_hash | TEXT | Not null |
| created_at | TEXT | Default datetime('now') |

---

## 5. Functions to Implement (`database/db.py`)

---

### A. `get_user_by_email(email)`

- Returns the matching `sqlite3.Row`, or `None` if there is no match
- Uses a parameterized query: `SELECT * FROM users WHERE email = ?`
- Closes the connection in `finally`

---

### B. `create_user(name, email, password)`

- Hashes `password` with `generate_password_hash` inside this function. The route never hashes
- Inserts into `users` with a parameterized query and commits
- Returns the new user's `id` (`cursor.lastrowid`)
- On `sqlite3.IntegrityError` (duplicate email), returns `None` instead of raising
- Closes the connection in `finally`

---

## 6. Changes to `app.py`

- Add `request`, `redirect`, `url_for` and `flash` to the Flask imports
- Import `create_user` and `get_user_by_email` from `database.db`
- Set `app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")`. `flash` needs this
- `register()` view:
    - **GET**: render `register.html`
    - **POST**:
        1. Read `name`, `email` and `password` from `request.form`
        2. Normalize: `name.strip()`, `email.strip().lower()`. Leave the password as entered
        3. Validate (see §10). On the first failure, re-render `register.html` with:
            - `error=<message>`
            - the entered `name` and `email`
            - HTTP status `400`
        4. If `get_user_by_email(email)` returns a user, re-render with the error "An account with that email already exists." and status `400`
        5. Call `create_user(...)`. If it returns `None` (race on the unique constraint), handle it the same way as step 4
        6. On success, call `flash("Account created — please sign in.")` and `redirect(url_for("login"))`
- The route contains no SQL

---

## 7. Files to Change

- `app.py`: imports, SECRET_KEY, `register()` handles GET and POST
- `database/db.py`: add `get_user_by_email()` and `create_user()`
- `templates/register.html`:
    - `action="/register"` → `action="{{ url_for('register') }}"`
    - Add `value="{{ name or '' }}"` to the name input
    - Add `value="{{ email or '' }}"` to the email input
    - Add `minlength="8"` to the password input
- `templates/login.html`:
    - Render flashed messages above the form using `get_flashed_messages()`
    - Change `action="/login"` to `url_for('login')`
- `static/css/style.css`: add an `.auth-success` class that mirrors `.auth-error` but uses success colours

---

## 8. Files to Create

- `tests/conftest.py`:
    - Provides an `app` fixture that monkeypatches `database.db.DB_PATH` to a `tmp_path` file
    - Calls `init_db()` on that file
    - Sets `app.config["TESTING"] = True`
    - pytest-flask then provides `client`
- `tests/test_registration.py`: the tests listed in §12

---

## 9. Dependencies

- No new pip packages
- Use:
    - `werkzeug.security.generate_password_hash`, which is already installed
    - `flask.flash`, `request`, `redirect` and `url_for`
    - `pytest` and `pytest-flask`, which are already in `requirements.txt`

---

## 10. Validation Rules

| Field | Rule | Error message |
| --- | --- | --- |
| name | Required after strip; ≤ 100 chars | "Please enter your name." |
| email | Required after strip; must match `^[^@\s]+@[^@\s]+\.[^@\s]+$` | "Please enter a valid email address." |
| password | Required; ≥ 8 characters | "Password must be at least 8 characters." |
| email | Must not already exist | "An account with that email already exists." |

- Validate in the order shown and report only the first error
- Server-side validation is authoritative. The HTML `required` and `minlength` attributes are only a convenience

---

## 11. Rules for Implementation

- All SQL lives in `database/db.py` and uses `?` placeholders only
- Never store or log plaintext passwords
- Never echo the password back into the form on error
- Store emails lowercased so uniqueness is case-insensitive
- Use `url_for()` for every redirect and every template link
- Do not set `session` values or log the user in. That is Step 3

---

## 12. Expected Behavior / Tests

- `GET /register` returns 200 and contains the form
- A valid POST does all of the following:
    - returns 302 to `/login`
    - creates a user row whose `password_hash != password`
    - makes `check_password_hash(hash, password)` return `True`
- Following the redirect shows "Account created — please sign in."
- Registering `Demo@Example.com` stores `demo@example.com`
- A duplicate email (including a different-case duplicate) returns 400 with the duplicate error, and the user count is unchanged
- Each of these returns 400 with the matching error:
    - missing name
    - invalid email
    - 7-character password
- When re-rendered after an error, the form contains the entered name and email but not the password

---

## 13. Error Handling Expectations

- Validation and duplicate errors re-render the form with status 400. They do not use `abort()`, because the user must see the form again
- A duplicate-email `IntegrityError` never becomes a 500
- Unexpected DB errors still raise, so they surface in debug mode

---

## 14. Definition of Done

- [ ] `POST /register` creates a user with a hashed password
- [ ] Duplicate emails are rejected case-insensitively, without a 500
- [ ] All validation rules in §10 are enforced server-side
- [ ] A successful registration redirects to login with a visible success message
- [ ] The form keeps name and email after an error
- [ ] No hardcoded URLs in `register.html` or `login.html`
- [ ] No SQL in `app.py`
- [ ] `pytest` passes, and the tests use a temp DB rather than `spendly.db`
- [ ] The app still starts on port 5001
