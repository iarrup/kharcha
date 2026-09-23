# Spec: Login and Logout

## Overview
Make sign-in and sign-out work with Flask's session. `GET /login` already renders the form and shows flashed messages from registration, but submitting it does nothing, and `/logout` returns a stub string. This step does four things:
- adds `POST /login`, which checks the email and password against the `users` table
- stores the user's identity in the signed session cookie
- replaces the `/logout` stub with a route that clears the session
- makes the navbar change depending on whether the user is logged in

This is the first step that knows who the user is. Steps 4 to 9 (profile and expense CRUD) all depend on it.

## Depends on
- Step 1: Database setup (`get_db()` and the `users` table)
- Step 2: Registration (`get_user_by_email()`, hashed passwords, `SECRET_KEY`, flashed messages in `login.html`)

## Routes
- `GET /login` — unchanged: renders `login.html`. A user who is already logged in is redirected to `profile` — public
- `POST /login` — **new**: validates the credentials, sets the session and redirects to `profile`. If the credentials are wrong, it re-renders the form with a generic error and status 401 — public
- `GET /logout` — **replaces the stub**: clears the session, flashes "You have been signed out." and redirects to `landing` — public (safe to call when not logged in)
- `GET /register` — **modified**: a user who is already logged in is redirected to `profile` — public

Do not implement `/profile` or any expense routes. They stay as stubs.

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email`, `password_hash`, `created_at`) is enough.

New helper in `database/db.py`:
- `authenticate_user(email, password)`:
  - looks up the user with `get_user_by_email(email)`
  - returns the `sqlite3.Row` if `check_password_hash(row["password_hash"], password)` is true
  - otherwise returns `None`
  - password checking stays in the DB layer, just as hashing does in `create_user()`

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html`: add `value="{{ email or '' }}"` to the email input so the email survives a failed attempt. Never echo the password back
  - `templates/base.html`: make the navbar depend on `session.user_id`:
    - **Logged in:** show the user's name (`session.user_name`) and a "Sign out" link to `url_for('logout')`
    - **Logged out:** keep the current "Sign in" and "Get started" links
  - `templates/landing.html`: show the flashed sign-out message. Put a `get_flashed_messages()` block in `base.html` above `{% block content %}` so every page shows flashes, and remove the duplicate loop from `login.html` so messages don't render twice

## Files to change
- `app.py`:
  - import `session` and `authenticate_user`
  - `login()` handles GET and POST
  - replace the `logout()` stub
  - add the logged-in redirect to `register()`
- `database/db.py`: add `authenticate_user()` and import `check_password_hash`
- `templates/base.html`: navbar that depends on the session, plus a shared flash-message block
- `templates/login.html`: keep the entered email and remove the per-page flash loop
- `static/css/style.css`: styles for the navbar user name and the shared flash block, using existing CSS variables only
- `CLAUDE.md`: in the routes table, mark `GET/POST /login` and `GET /logout` as implemented (Step 3)

## Files to create
- `tests/test_auth.py`: login and logout tests (see Definition of done). Reuse the existing `app` fixture in `tests/conftest.py`, which already points the DB at a temp file

## New dependencies
No new dependencies. Use `flask.session` and `werkzeug.security.check_password_hash`, which are already installed.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders). No SQL in `app.py`
- Passwords hashed with werkzeug. Verify them with `check_password_hash` inside `database/db.py`
- Use CSS variables. Never hardcode hex values
- All templates extend `base.html`
- Use `url_for()` for every redirect and template link
- Login POST flow:
  1. Read `email` and `password`
  2. Normalise the email with `.strip().lower()`, as registration does
  3. If either field is empty, or `authenticate_user` returns `None`, re-render with `error="Invalid email or password."`, the entered `email`, and status 401
  4. Use the same message whether the email is unknown or the password is wrong, so the error does not reveal whether an account exists
- On success:
  1. call `session.clear()` first, to prevent session fixation
  2. set `session["user_id"]` and `session["user_name"]`
  3. redirect to `url_for("profile")`
- Never store the password or the password hash in the session
- Logout uses `session.clear()`, not a `pop` of individual keys
- Do not add a `login_required` decorator or protect `/profile` yet. That is Step 4
- Keep port 5001 and the existing `SECRET_KEY` config unchanged

## Definition of done
- [ ] Signing in as `demo@spendly.com` / `demo123` redirects (302) to `/profile`
- [ ] After login, the navbar shows "Demo User" and a "Sign out" link, and hides "Sign in" and "Get started"
- [ ] Signing in with `DEMO@Spendly.com ` (mixed case, trailing space) also succeeds
- [ ] A wrong password returns 401 with "Invalid email or password.", and the email field keeps its value while the password field is empty
- [ ] An unknown email returns 401 with the same message
- [ ] An empty email or password returns 401 without a 500
- [ ] After login, the session holds only `user_id` and `user_name`, with no password or hash
- [ ] Visiting `/logout` clears the session, redirects to `/`, and shows "You have been signed out."
- [ ] Visiting `/logout` when not logged in still redirects cleanly (no 500)
- [ ] Visiting `/login` or `/register` while logged in redirects to `/profile`
- [ ] Registering a new account and then signing in with it works end to end
- [ ] The registration success message still appears once (not twice) on `/login`
- [ ] No hardcoded URLs in the templates and no SQL in `app.py`
- [ ] `pytest` passes: the existing registration tests plus the new `tests/test_auth.py`
- [ ] The app starts with `python app.py` on port 5001
