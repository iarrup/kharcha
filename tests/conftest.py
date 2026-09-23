import pytest

import database.db as db


@pytest.fixture
def app(tmp_path, monkeypatch):
    # Patch DB_PATH before importing the app so its module-level
    # init_db()/seed_db() never touch the real spendly.db.
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    from app import app as flask_app

    db.init_db()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def user_count():
    def count():
        conn = db.get_db()
        try:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        finally:
            conn.close()
    return count
