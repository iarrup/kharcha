# Step 2 — Registration: Implementation Plan

## Context
`GET /register` renders a form, but POSTing it does nothing (the route is GET-only). This step implements `.claude/specs/02-registration.md`:

- validate input
- create the user with a hashed password
- redirect to `/login` with a flashed success message

It does **not** implement login or session handling; those are Step 3.

Current state:
- `app.py` has no `SECRET_KEY`, and `init_db()`/`seed_db()` run at module import.
- `database/db.py` has no user helpers.
- `register.html` and `login.html` hardcode form actions.
- `base.html` doesn't render flashes.
- No test suite exists.

## Step 1: `database/db.py`
Add two helpers after `get_db()`. Reuse the existing `get_db()`, `sqlite3` and `generate_password_hash` imports; no new imports are needed.

- **`get_user_by_email(email) -> sqlite3.Row | None`**
  - `conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()`
  - Close the connection in `finally`.
- **`create_user(name, email, password) -> int | None`**
  - Hash the password first, then `INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)`.
  - `commit`, then `return cur.lastrowid`.
  - `except sqlite3.IntegrityError: return None`. Catch only that exception, so other database errors still raise.
  - Close the connection in `finally`.

## Step 2: `app.py`
- **Imports:**
  - `os` and `re`
  - `request`, `redirect`, `url_for`, `flash` from flask
  - `create_user`, `get_user_by_email` from `database.db`
- **Secret key:** `app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")`, placed right after `app = Flask(__name__)`.
- **Constants:**
  - `EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")`
  - `DUPLICATE_EMAIL_ERROR = "An account with that email already exists."`
- **Helper:** `validate_registration(name, email, password) -> str | None`. It is pure logic with no DB access, and returns the first error in spec §10 order:
  1. Empty name, or name over 100 characters.
  2. Email that doesn't match `EMAIL_RE`.
  3. Password under 8 characters.

  It keeps the route thin and can be unit-tested.
- **`register()`:** change it to `methods=["GET", "POST"]`.
  - **GET:** render the form.
  - **POST:**
    1. Read the fields with `request.form.get(key, "")`, never `[]`.
    2. Normalize: `name.strip()` and `email.strip().lower()`.
    3. Run `validate_registration`.
    4. If valid, pre-check `get_user_by_email` and set the duplicate error on a match.
    5. Call `create_user`. If it returns `None` (lost race), set the duplicate error.
    6. On any error: `return render_template("register.html", error=error, name=name, email=email), 400`. Never pass the password back.
    7. On success: `flash("Account created — please sign in.")` (em dash U+2014), then `redirect(url_for("login"))`.
- Leave `login()` and the Step 3+ stubs untouched.

## Step 3: Templates
- **`templates/register.html`:**
  - `action="{{ url_for('register') }}"`
  - Name input gets `value="{{ name or '' }}"`.
  - Email input gets `value="{{ email or '' }}"`.
  - Password input gets `minlength="8"` and no `value`.
- **`templates/login.html`:**
  - Above the `{% if error %}` block: `{% for message in get_flashed_messages() %}<div class="auth-success">{{ message }}</div>{% endfor %}`
  - `action="{{ url_for('login') }}"`. POST /login will return 405 until Step 3; that's expected.

## Step 4: `static/css/style.css`
Add `.auth-success` right after `.auth-error` (around line 486):
- Same box model as `.auth-error`.
- `background: var(--accent-light)` and `color: var(--accent)`.
- `border: 1px solid #c3d9ca`.

## Step 5: Tests
New files:
- **`tests/__init__.py`** (empty). Without it, a bare `pytest` puts `tests/` rather than the project root on `sys.path`, and `from app import app` fails.
- **`tests/conftest.py`:** an `app` fixture that runs in this order:
  1. `monkeypatch.setattr(database.db, "DB_PATH", str(tmp_path / "test.db"))`
  2. `from app import app as flask_app`, imported **inside** the fixture after the patch, so the module-level `init_db()`/`seed_db()` never touch the real `spendly.db`.
  3. `db.init_db()`
  4. `flask_app.config["TESTING"] = True`

  pytest-flask supplies `client`. Add a small `user_count()` helper. Note that the first test's database contains the seeded demo user, so assert on relative counts only.
- **`tests/test_registration.py`:** tests mapped to spec §12/§13. Use `resp.get_data(as_text=True)` for text assertions, because of the em dash.
  1. GET /register returns 200 and contains the form.
  2. A valid POST returns 302 with `Location == "/login"`.
  3. The stored hash is not the plaintext, and `check_password_hash` passes.
  4. Following the redirect shows the flash text inside `.auth-success`.
  5. `Demo@Example.com` is stored as `demo@example.com`.
  6. A duplicate email returns 400 with the duplicate error, and the user count is unchanged.
  7. A different-case duplicate gets the same result as test 6.
  8. A whitespace-only name returns 400 with "Please enter your name."
  9. An invalid email returns 400 with "Please enter a valid email address."
  10. A 7-character password returns 400 with "Password must be at least 8 characters.", and no row is created.
  11. Sticky form: send an invalid email with password `UniquePw12345`. The response contains `value="Ada Lovelace"` and the entered email, and does not contain `UniquePw12345`.
  12. Race case: patch `sys.modules["app"].get_user_by_email` to return `None`, pre-insert the user, then POST. Expect 400 with the duplicate error, not 500.
  13. A 101-character name returns 400.

## Step 6: Housekeeping
- Update the CLAUDE.md route table: `/register` becomes "GET/POST — implemented (Step 2)".
- Add `.pytest_cache/` to `.gitignore` if it isn't already there.

## Verification
1. Record the `sha1sum spendly.db` hash before running tests.
2. Run `.venv/bin/pytest -v`. Everything should pass. Also run `.venv/bin/python -m pytest`.
3. Check that the `spendly.db` hash is unchanged and that `git status` shows no stray `.db` files.
4. Run two greps, both of which should return nothing:
   - `grep -nE "SELECT|INSERT" app.py`
   - `grep -n 'action="/' templates/*.html`
5. Manual test: run `.venv/bin/python app.py` and open `http://127.0.0.1:5001/register`.
   - A valid signup lands on the login page with a green banner.
   - A duplicate email in different case shows a red error, keeps the name and email, and clears the password.
   - Run `curl -i -d 'name=A&email=a@b.co&password=1234567' http://127.0.0.1:5001/register`. It should return 400.
6. Per the CLAUDE.md subagent policy, a subagent independently re-runs and verifies the test results.
