# Step 1: Database Setup — Implementation Plan

## Context

Spendly's `database/db.py` is currently just a comment scaffold (no code) and `app.py` never touches the database. Every future feature — auth, profile, expense CRUD — depends on a working data layer first. This step, defined in `.claude/specs/01-database-setup.md`, replaces the stub with a real SQLite implementation (`get_db()`, `init_db()`, `seed_db()`) and wires it into `app.py`'s startup so the schema and demo data exist before any route runs. No routes, templates, or stub behavior change in this step — stub routes (`/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) stay exactly as raw-string placeholders, per CLAUDE.md's "do not implement a stub route unless the active task explicitly targets that step."

## Decisions confirmed with user

- **DB filename: `spendly.db`** (matches product name). Requires adding a new line to `.gitignore` since it currently only lists `expense_tracker.db`.
- **Seed dates: computed from `datetime.now()`** — year/month taken live at seed time, with fixed day-of-month values, so "current month" stays true no matter when the app is first run, while remaining deterministic once seeded (idempotent).

## Files to change

1. `database/db.py` — implement `get_db()`, `init_db()`, `seed_db()`
2. `app.py` — import and call `init_db()`/`seed_db()` at startup
3. `.gitignore` — add `spendly.db`

No new files are created.

---

## 1. `database/db.py`

```python
import os
import sqlite3
from datetime import datetime

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "spendly.db"))

CATEGORIES = ["Food", "Transport", "Bills", "Health",
              "Entertainment", "Shopping", "Other"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        conn.commit()
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing > 0:
            return

        password_hash = generate_password_hash("demo123")
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", password_hash),
        )
        user_id = cursor.lastrowid

        today = datetime.now()
        year, month = today.year, today.month

        # 8 expenses covering all 7 categories at least once (Food appears
        # twice); days kept <=28 to stay valid for every month.
        sample_expenses = [
            (user_id, 45.50, "Food", f"{year:04d}-{month:02d}-02", "Groceries"),
            (user_id, 12.00, "Transport", f"{year:04d}-{month:02d}-04", "Bus fare"),
            (user_id, 89.99, "Bills", f"{year:04d}-{month:02d}-05", "Electricity bill"),
            (user_id, 25.00, "Health", f"{year:04d}-{month:02d}-08", "Pharmacy"),
            (user_id, 15.75, "Entertainment", f"{year:04d}-{month:02d}-11", "Movie ticket"),
            (user_id, 60.00, "Shopping", f"{year:04d}-{month:02d}-14", "New shoes"),
            (user_id, 30.00, "Food", f"{year:04d}-{month:02d}-17", "Restaurant dinner"),
            (user_id, 10.00, "Other", f"{year:04d}-{month:02d}-20", "Miscellaneous"),
        ]

        conn.executemany(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            sample_expenses,
        )
        conn.commit()
    finally:
        conn.close()
```

Key points:
- `DB_PATH` resolves relative to `db.py`'s own location (`os.path.dirname(os.path.abspath(__file__))`), so it always lands at `<repo_root>/spendly.db` regardless of the process's working directory.
- `PRAGMA foreign_keys = ON` runs inside `get_db()` itself — this is a per-connection SQLite setting, not persisted in the file, so it must be set on every connection, not just once in `init_db()`.
- `init_db()` and `seed_db()` each open and close their own connection in a `try/finally`, so no connections leak even if a statement raises.
- Idempotency: `seed_db()` checks `SELECT COUNT(*) FROM users` and returns early if any row exists — matches the spec's described approach exactly.
- All SQL uses `?` placeholders; no f-strings or string concatenation in any query.
- `get_db()` stays a plain stateless factory (no `flask.g` caching) — the spec doesn't ask for request-scoped reuse, and no route calls it yet in this step, so adding that now would be speculative.

---

## 2. `app.py`

Add one import line and one startup block, placed **immediately after `app = Flask(__name__)`, at module level** — not inside `if __name__ == "__main__":`. This ensures the DB is ready whenever `app.py` is imported (via `python app.py`, `flask run`, or a future test client), not only when run as a script.

```python
from flask import Flask, render_template

from database.db import get_db, init_db, seed_db

app = Flask(__name__)

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #
... (unchanged — all existing and stub routes stay exactly as they are) ...


if __name__ == "__main__":
    app.run(debug=True, port=5001)
```

`get_db` is imported now even though no route calls it yet, since the spec explicitly lists it as one of the three required imports — it's ready for stub routes implemented in later steps without another import edit.

---

## 3. `.gitignore`

Add `spendly.db` as a new line (keep the existing `expense_tracker.db` entry — harmless to leave):

```
venv/
expense_tracker.db
spendly.db
__pycache__/
*.pyc
*.pyo
.env
.DS_Store
.claude/plans/
```

---

## Verification (manual — no test suite exists yet, none is created in this step)

Run from repo root after implementing:

1. **Fresh startup creates the DB file**
   ```bash
   rm -f spendly.db
   python app.py &
   sleep 1 && kill %1
   ls -la spendly.db
   ```

2. **Schema matches spec**
   ```bash
   sqlite3 spendly.db ".schema users"
   sqlite3 spendly.db ".schema expenses"
   ```
   Confirm PK autoincrement, `UNIQUE` email, `NOT NULL` flags, and the FK clause on `expenses.user_id`.

3. **Seed data correctness**
   ```bash
   sqlite3 spendly.db "SELECT id, name, email FROM users;"
   sqlite3 spendly.db "SELECT COUNT(*) FROM expenses;"
   sqlite3 spendly.db "SELECT category, COUNT(*) FROM expenses GROUP BY category;"
   ```
   Expect 1 user (Demo User / demo@spendly.com, hashed password — not plaintext), 8 expense rows, all 7 categories present, dates in the current `YYYY-MM`.

4. **Idempotency — re-run, confirm no duplication**
   ```bash
   python app.py &
   sleep 1 && kill %1
   sqlite3 spendly.db "SELECT COUNT(*) FROM users;"     # still 1
   sqlite3 spendly.db "SELECT COUNT(*) FROM expenses;"  # still 8
   ```

5. **UNIQUE constraint enforced**
   ```bash
   sqlite3 spendly.db "INSERT INTO users (name, email, password_hash) VALUES ('X','demo@spendly.com','y');"
   ```
   Expect `UNIQUE constraint failed: users.email`.

6. **Foreign key constraint enforced** (CLI needs the pragma explicitly, unlike the app's own connections)
   ```bash
   sqlite3 spendly.db "PRAGMA foreign_keys=ON; INSERT INTO expenses (user_id, amount, category, date) VALUES (9999, 10.0, 'Food', '2026-09-01');"
   ```
   Expect `FOREIGN KEY constraint failed`.

7. **App still starts and serves existing pages**
   ```bash
   python app.py &
   sleep 1
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5001/
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5001/register
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5001/logout
   kill %1
   ```
   All should return 200; app must not crash on `init_db()`/`seed_db()`.

8. **Row access sanity check**
   ```bash
   python -c "
   from app import app
   from database.db import get_db
   with app.app_context():
       conn = get_db()
       row = conn.execute('SELECT * FROM users').fetchone()
       print(dict(row))
       conn.close()
   "
   ```
   Confirms `row_factory = sqlite3.Row` gives dict-like access.
