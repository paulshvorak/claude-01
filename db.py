import json
import sqlite3
from contextlib import contextmanager

from config import DB_PATH


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_table(table: str) -> None:
    with connect() as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                external_id TEXT PRIMARY KEY,
                fetched_at  TEXT NOT NULL,
                payload     TEXT NOT NULL,
                sent_at     TEXT
            )
        """)


def insert_new(table: str, items: list) -> None:
    with connect() as conn:
        conn.executemany(
            f"INSERT OR IGNORE INTO {table} (external_id, fetched_at, payload) VALUES (?, ?, ?)",
            [(item.external_id, item.fetched_at, json.dumps(item.payload)) for item in items],
        )


def get_unsent(table: str) -> list[dict]:
    with connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT external_id, fetched_at, payload FROM {table} WHERE sent_at IS NULL"
        ).fetchall()
    return [
        {"external_id": row["external_id"], "fetched_at": row["fetched_at"], "payload": json.loads(row["payload"])}
        for row in rows
    ]


def get_all(table: str) -> list[dict]:
    with connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT external_id, fetched_at, payload FROM {table}").fetchall()
    return [
        {"external_id": row["external_id"], "fetched_at": row["fetched_at"], "payload": json.loads(row["payload"])}
        for row in rows
    ]


def mark_sent(table: str, external_ids: list[str], sent_at: str) -> None:
    if not external_ids:
        return
    with connect() as conn:
        conn.executemany(
            f"UPDATE {table} SET sent_at = ? WHERE external_id = ?",
            [(sent_at, external_id) for external_id in external_ids],
        )
