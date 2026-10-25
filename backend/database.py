"""SQLite 저장과 조회. 수집이 끝난 데이터만 한 번에 교체한다."""

from contextlib import closing
from pathlib import Path
import sqlite3

from .config import now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    source_count INTEGER,
    stored_count INTEGER,
    duplicate_count INTEGER,
    error_message TEXT
);
CREATE TABLE IF NOT EXISTS programs (
    id INTEGER PRIMARY KEY,
    content_hash TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    target_text TEXT NOT NULL,
    application_start TEXT,
    application_end TEXT,
    schedule_start TEXT,
    schedule_end TEXT,
    source_status TEXT NOT NULL,
    organizer TEXT NOT NULL,
    contact_phone TEXT,
    homepage_url TEXT,
    source_registered_at TEXT,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    sync_run_id INTEGER NOT NULL REFERENCES sync_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_programs_category ON programs(active, category);
CREATE INDEX IF NOT EXISTS idx_programs_deadline ON programs(active, application_end);
"""


def connect(path):
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as connection:
        connection.executescript(SCHEMA)
        connection.commit()


def start_sync(path):
    with closing(connect(path)) as connection:
        cursor = connection.execute(
            "INSERT INTO sync_runs(started_at, status) VALUES (?, 'running')", (now_iso(),)
        )
        connection.commit()
        return cursor.lastrowid


def fail_sync(path, run_id, message):
    with closing(connect(path)) as connection:
        connection.execute(
            "UPDATE sync_runs SET finished_at=?, status='failed', error_message=? WHERE id=?",
            (now_iso(), message, run_id),
        )
        connection.commit()


def save_snapshot(path, records, run_id, source_count):
    if not records:
        raise ValueError("Empty snapshot")
    fields = list(records[0])
    update_fields = [name for name in fields if name != "content_hash"]
    sql = (
        f"INSERT INTO programs({','.join(fields)}, active, sync_run_id) "
        f"VALUES ({','.join('?' for _ in fields)}, 1, ?) "
        "ON CONFLICT(content_hash) DO UPDATE SET "
        + ",".join(f"{name}=excluded.{name}" for name in update_fields)
        + ",active=1,sync_run_id=excluded.sync_run_id"
    )
    # fields comes only from our normalizer, never from an HTTP request.
    with closing(connect(path)) as connection:
        with connection:
            connection.execute("UPDATE programs SET active=0")
            connection.executemany(sql, [tuple(item[name] for name in fields) + (run_id,) for item in records])
            count = connection.execute("SELECT COUNT(*) FROM programs WHERE active=1").fetchone()[0]
            connection.execute(
                "UPDATE sync_runs SET finished_at=?, status='success', source_count=?, "
                "stored_count=?, duplicate_count=? WHERE id=?",
                (now_iso(), source_count, count, source_count - count, run_id),
            )
    return count


def list_programs(path, category=None):
    sql, params = "SELECT * FROM programs WHERE active=1", []
    if category:
        sql += " AND category=?"
        params.append(category)
    with closing(connect(path)) as connection:
        return [dict(row) for row in connection.execute(sql, params)]


def find_program(path, program_id):
    with closing(connect(path)) as connection:
        row = connection.execute("SELECT * FROM programs WHERE active=1 AND id=?", (program_id,)).fetchone()
        return dict(row) if row else None


def latest_sync(path):
    with closing(connect(path)) as connection:
        row = connection.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None
