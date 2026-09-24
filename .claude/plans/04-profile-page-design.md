# Step 4 — Profile Page Design: Implementation Plan

## Context
`/profile` (`app.py:111-113`) is still a stub that returns a raw string, even though login and register redirect to it. This plan implements `.claude/specs/04-profile-page-design.md`: a protected profile page built from hardcoded data (no DB queries), ready for Step 5 to swap in real data.

The page follows `.claude/skills/frontend-design/SKILL.md`:
- Reuse the existing tokens and fonts (these override the skill's default palette).
- Put page-prefixed classes in their own `profile.css`.
- Use a 4/8px spacing scale and a 12/14/16/20/24/32px type scale.
- Use borders, not shadows.
- Use `tabular-nums` for amounts.
- Give table rows a hover state and right-align the numbers.
- Stack the layout and scroll the table sideways below 768px.

**Your decision:** no icons (no Lucide, no inline SVG). `base.html`, `main.js`, `style.css` and `database/db.py` stay untouched.

**Note:** the earlier Step 4 code isn't anywhere in git (`feature/profile-page-design` only has the skill and a `CLAUDE.md` edit). This plan reuses that version's proven decisions but doesn't depend on it.

## UI plan
- **Header:** H1 "Your profile" in `--font-display`, a muted subtitle, left-aligned in a container of width `--max-width`.
- **User card:** a 64px round avatar showing the initials (`--accent-light` background, `--accent` text), then name, email and "Member since January 2026".
- **Stats row:** three tiles:
  - Total spent: ₹11,000.00
  - Transactions: 8
  - Top category: Food, with "₹4,300.00 · 39% of spend" underneath
- **Main grid** (2fr / 1fr):
  - Transactions table: Date, Description, Category badge, Amount (right-aligned).
  - Category breakdown: 7 rows, largest first. Each shows name, amount and %, with a thin `--accent` bar.
- **Assumptions:**
  - The data mirrors the seeded demo account (Demo User / demo@spendly.com) with September 2026 expenses.
  - Bar width is each category's share of the total.
  - Only the badges vary in colour.

## Step 1: `app.py`
- **Import:** add `CATEGORIES` to the existing `database.db` import. This is only the list of names, not a DB call.
- **Constants** (after `LOGIN_ERROR`):
  - `PROFILE_USER = {"name": "Demo User", "email": "demo@spendly.com", "initials": "DU", "member_since": "January 2026"}`
  - `PROFILE_EXPENSES`: 8 dicts with keys `date` (ISO), `date_label` ("18 Sep 2026"), `description`, `category` and `amount`. Newest first:

    | Date | Description | Category | Amount (₹) |
    |---|---|---|---|
    | 2026-09-18 | Restaurant dinner | Food | 1,850 |
    | 2026-09-15 | Birthday gift | Other | 1,100 |
    | 2026-09-12 | Movie tickets | Entertainment | 450 |
    | 2026-09-10 | Running shoes | Shopping | 1,500 |
    | 2026-09-08 | Pharmacy | Health | 650 |
    | 2026-09-05 | Electricity bill | Bills | 2,200 |
    | 2026-09-04 | Metro card top-up | Transport | 800 |
    | 2026-09-02 | Groceries | Food | 2,450 |

    I checked the arithmetic by hand. The total is ₹11,000 and all 7 categories appear:

    | Category | Total (₹) | Share | Bar width |
    |---|---|---|---|
    | Food | 4,300 | 39% | 40% |
    | Bills | 2,200 | 20% | 20% |
    | Shopping | 1,500 | 14% | 15% |
    | Other | 1,100 | 10% | 10% |
    | Transport | 800 | 7% | 5% |
    | Health | 650 | 6% | 5% |
    | Entertainment | 450 | 4% | 5% |
- **`summarize_expenses(expenses)`**, a pure helper in the Helpers section. It returns `{"total", "count", "top_category", "categories"}`:
  - `categories` is sorted by amount, largest first. Each item is `{"name", "slug", "amount", "percent", "bar_step"}`.
  - `top_category` is the first item, or `None`.
  - `slug` is `name.lower()` when the name is in `CATEGORIES`, otherwise `"other"`.
  - `percent = round(amount / total * 100)`.
  - `bar_step = max(5, min(100, 5 * round(amount / total * 20)))`.
  - An empty list gives total 0, count 0, `top_category=None` and `categories=[]`.
- **Route:** move it out of the "Placeholder routes" banner and put it after `privacy()`:
  ```python
  @app.route("/profile")
  def profile():
      if not session.get("user_id"):
          return redirect(url_for("login"))
      return render_template("profile.html", user=PROFILE_USER,
                             expenses=PROFILE_EXPENSES,
                             summary=summarize_expenses(PROFILE_EXPENSES))
  ```

## Step 2: `templates/profile.html` (new)
- **Wrapper:** `{% extends "base.html" %}`, title `Profile — Spendly`.
- **Stylesheet:** `{% block head %}` links `url_for('static', filename='css/profile.css')`.
- **Money format:** `{{ "₹{:,.2f}".format(x) }}`. Type the literal `₹`, not a hex entity.
- **Class names:** every class uses the `profile-` prefix, with BEM-style `__` for parts and `--` for variants.
- **Structure:**
  ```
  section.profile > div.profile-container
    header.profile-header > h1.profile-title + p.profile-subtitle
    section.profile-card.profile-user[aria-label]
      div.profile-user__avatar[aria-hidden] · div.profile-user__info > p.__name, p.__email, p.__meta
    section.profile-stats[aria-label] > 3× div.profile-card.profile-stat > p.__label, p.__value[, p.__sub]
    div.profile-grid
      section.profile-card.profile-transactions > h2.profile-section-title
        div.profile-table-wrap > table.profile-table
          th.profile-table__num for Amount; tbody tr.profile-table__row:
          <time datetime>date_label</time> · description · span.profile-badge.profile-badge--{slug} · td.profile-table__num
      section.profile-card.profile-breakdown > h2.profile-section-title
        ul.profile-breakdown__list > li.profile-breakdown__item
          div.profile-breakdown__head > span.__name + span.__amount ("₹… · N%")
          div.profile-bar[aria-hidden] > div.profile-bar__fill.profile-bar__fill--w-{bar_step}
  ```
- **Rules:**
  - No `style=`, no hex values, no hardcoded URLs.
  - No extra flash block (`base.html` already has one).

## Step 3: `static/css/profile.css` (new, existing tokens only)
- **Scales:**
  - Type: 0.75 / 0.875 / 1 / 1.25 / 1.5 / 2rem.
  - Spacing: 0.25 / 0.5 / 0.75 / 1 / 1.5 / 2 / 3rem.
- **Layout:**
  - `.profile`: padding `3rem 2rem 4rem`.
  - `.profile-container`: `--max-width`, centred, a flex column with a 1.5rem gap.
- **Cards** (`.profile-card`): `--paper-card` background, 1px `--border`, `--radius-md`, 1.5rem padding, no shadow.
- **Text:**
  - `.profile-title`: display font, 2rem.
  - `.profile-subtitle`: 0.875rem, muted.
  - Name: 1.25rem, weight 600. Email: 0.875rem, `--ink-soft`. Meta line: 0.75rem, muted.
- **Stats:**
  - `.profile-stats`: grid of `repeat(3, minmax(0,1fr))`, 1rem gap.
  - Labels: 0.75rem, uppercase, muted.
  - Values: 1.5rem, weight 600, `tabular-nums`.
- **Grid** (`.profile-grid`): `minmax(0,2fr) minmax(0,1fr)`, 1.5rem gap, `align-items: start`.
- **Table:**
  - `.profile-table-wrap`: `overflow-x: auto`, bleeds to the card edges with a negative margin.
  - `th`: 0.75rem, uppercase, muted, `--border` bottom border.
  - `td`: 0.75rem 1rem padding, `--border-soft` bottom border.
  - `tbody tr:hover`: `var(--paper)` background.
  - `.profile-table__num`: right-aligned, `tabular-nums`, `nowrap`.
- **Badges:**
  - `.profile-badge`: pill shape, 999px radius, 0.75rem, weight 500.
  - Colour pairs:

    | Category | Text | Background |
    |---|---|---|
    | food, shopping | `--accent` | `--accent-light` |
    | bills, entertainment | `--accent-2` | `--accent-2-light` |
    | health | `--danger` | `--danger-light` |
    | transport | `--ink-soft` | `--paper-warm` |
    | other | `--ink-muted` | `--border-soft` |
- **Bars:**
  - `.profile-bar`: 0.5rem tall, `--border-soft` track, rounded.
  - `.profile-bar__fill`: `--accent`.
  - 20 width classes, `.profile-bar__fill--w-5` … `--w-100`.
- **Breakpoints:**
  - At 900px, `.profile-grid` becomes a single column.
  - At 768px:
    - The page padding shrinks to `2rem 1rem 3rem`.
    - Stats become a single column and card padding drops to 1rem.
    - The table gets `min-width: 560px`, so it scrolls inside its card.
    - The title drops to 1.5rem.

## Step 4: `tests/test_profile.py` (new)
- **Import rule:** never import `app` at the module top level, because it would run `init_db()` / `seed_db()` against the real `spendly.db`.
- **Fixtures:**
  - `profile_mod(app)` returns `importlib.import_module("app")` after the conftest fixture has patched `DB_PATH`.
  - `logged_in(client)` sets `user_id=1` and `user_name="Ada Lovelace"` through `session_transaction()`. The name is different from the card's "Demo User", so the navbar check can't pass by accident.

Tests:
1. A logged-out user gets a 302 to `/login`.
2. A logged-in user gets a 200.
3. The user card shows the name, email, "Member since" and "DU".
4. The stats show `₹11,000.00`, "Transactions" and "Food".
5. The table has 8 `profile-table__row` rows (at least 3).
6. The breakdown has 7 `profile-breakdown__item` rows (at least 3).
7. The navbar shows "Ada Lovelace" and "Sign out", and doesn't show "Get started".
8. The page contains `profile-badge--food`, and the rendered page has no `style=`.
9. The page links `css/profile.css`.
10. `profile.html` and `profile.css` contain no hex values.
11. `profile.css` defines a `.profile-badge--{slug}` for every name in `CATEGORIES`.
12. `summarize_expenses(PROFILE_EXPENSES)`: total 11000, count 8, top category Food, percents add up to 100, sorted largest first, and every `bar_step` is a multiple of 5 between 5 and 100.
13. `summarize_expenses([])` returns the empty shape.
14. With `db.get_db` monkeypatched to raise, `/profile` still returns 200, which proves the route makes no DB calls.

## Step 5: Housekeeping
- `CLAUDE.md` routes table: `GET /profile` becomes "Implemented (Step 4) — profile page with hardcoded data".
- `CLAUDE.md` architecture tree: add `profile.css  # Profile-page-only styles`.

## Verification
1. `.venv/bin/pytest -q` should pass: the 31 existing tests plus the new ones.
2. These greps should all print nothing:
   - `grep -nE '#[0-9a-fA-F]{3,8}\b' templates/profile.html static/css/profile.css`
   - `grep -n 'style=' templates/profile.html`
   - `grep -nE 'href="/|src="/' templates/profile.html`
   - `grep -nEi 'get_db|select |execute\(' app.py`
3. `md5sum spendly.db` should give the same value (`9dec1878…`) before and after the test run.
4. Manual check: run `.venv/bin/python app.py` on port 5001.
   - Logged out, `/profile` redirects to `/login`.
   - Sign in as demo@spendly.com / demo123.
   - Check the layout at desktop width, at 768px (stacked, table scrolls sideways) and at 375px (no page overflow).
   - Check the row hover and that amounts are aligned.
5. Per CLAUDE.md, a subagent re-runs the tests and greps on its own and reports the results.
