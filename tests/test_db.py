import sqlite3

import pytest

from app.infra.db import Database


def test_new_database_gets_every_migration(tmp_path):
    db = Database(tmp_path / "a.db")
    assert db.version == 2
    tables = {r["name"] for r in db.all("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"events", "cards", "slots", "captures", "sessions"} <= tables
    db.close()
    assert Database(tmp_path / "a.db").version == 2  # reopening applies nothing twice


def test_database_from_before_migrations_keeps_its_data(tmp_path):
    """data/alpr.db files created by the old code have the tables but user_version 0."""
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(
        "CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, plate TEXT NOT NULL, display TEXT NOT NULL,"
        " direction TEXT NOT NULL, gate TEXT NOT NULL DEFAULT 'main', confidence REAL NOT NULL, image_path TEXT,"
        " created_at TEXT NOT NULL);"
        "INSERT INTO events (plate, display, direction, confidence, created_at)"
        " VALUES ('51G12345', '51G-123.45', 'in', 0.9, '2026-10-14T08:00:00');"
    )
    old.commit()
    old.close()
    db = Database(path)
    assert db.version == 2
    assert db.scalar("SELECT COUNT(*) FROM events") == 1


def test_new_migration_file_is_applied(tmp_path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_a.sql").write_text("CREATE TABLE a (x INTEGER);")
    db = Database(tmp_path / "m.db", migrations)
    (migrations / "002_b.sql").write_text("ALTER TABLE a ADD COLUMN y TEXT;")
    db.migrate(migrations)
    assert db.version == 2
    db.execute("INSERT INTO a (x, y) VALUES (1, 'ok')")


def test_transaction_rolls_back_on_error(tmp_path):
    db = Database(tmp_path / "t.db")
    with pytest.raises(RuntimeError):
        with db.transaction():
            db.execute("INSERT INTO cards (id) VALUES (1)")
            with db.transaction():  # nested: joins the outer one
                db.execute("INSERT INTO cards (id) VALUES (2)")
            raise RuntimeError("boom")
    assert db.scalar("SELECT COUNT(*) FROM cards") == 0
