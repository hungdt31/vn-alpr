"""SQLite access shared by every repository: one connection, transactions and schema migrations.

Migrations are the numbered files in infra/migrations (001_*.sql, 002_*.sql, ...). The database remembers the
last one applied in PRAGMA user_version, so adding a table or a column means adding a new file, never editing
an old one or deleting the database.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    def __init__(self, path: str | Path, migrations_dir: Path = MIGRATIONS_DIR):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # FastAPI runs sync endpoints in a thread pool: one shared connection, serialized by a re-entrant lock
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()
        self._depth = 0
        self.migrate(migrations_dir)

    def close(self) -> None:
        self._conn.close()

    # ---- schema ---------------------------------------------------------------------------------
    @property
    def version(self) -> int:
        return self._conn.execute("PRAGMA user_version").fetchone()[0]

    def migrate(self, migrations_dir: Path) -> None:
        """Apply, in order, every migration newer than the database."""
        files = sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql"))
        with self._lock:
            for f in files:
                number = int(f.name[:3])
                if number <= self.version:
                    continue
                # executescript commits on its own, so the version bump is part of the same script
                sql = f.read_text(encoding="utf-8")
                self._conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")

    # ---- queries --------------------------------------------------------------------------------
    @contextmanager
    def transaction(self) -> Iterator[None]:
        """All writes inside commit together or not at all. Nested blocks join the outer transaction."""
        with self._lock:
            outer = self._depth == 0
            if outer:
                self._conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield
            except BaseException:
                self._depth -= 1
                if outer:
                    self._conn.execute("ROLLBACK")
                raise
            self._depth -= 1
            if outer:
                self._conn.execute("COMMIT")

    def execute(self, sql: str, args: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, args)

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> None:
        with self._lock:
            self._conn.executemany(sql, rows)

    def one(self, sql: str, args: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, args).fetchone()

    def all(self, sql: str, args: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, args).fetchall()

    def scalar(self, sql: str, args: Sequence[Any] = ()) -> Any:
        row = self.one(sql, args)
        return row[0] if row else None
