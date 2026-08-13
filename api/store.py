"""Two small stores: what we have already extracted, and what humans corrected.

Both exist so the system stops repeating itself — the first stops it re-reading a document
it has already seen, the second stops it repeating a mistake a person already fixed.

SQLite because it is one file, ships with Python, survives a restart, and handles the one
concurrency case that matters here: two uploads of the same invoice arriving at once.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

DB = Path("data/store.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS extractions (
    sha256      TEXT PRIMARY KEY,
    filename    TEXT,
    result      TEXT NOT NULL,          -- the whole Extraction as JSON
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS corrections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256      TEXT NOT NULL,
    field       TEXT NOT NULL,
    was         TEXT,                   -- what we said
    now         TEXT NOT NULL,          -- what the human said
    box         TEXT,                   -- where the correct value actually sat
    created_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS corrections_field ON corrections(field);
"""


def connect(path: Path = DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# ---------------------------------------------------------------- step 1: dedup

def file_hash(data: bytes) -> str:
    """SHA-256 of the file bytes.

    Only catches literal re-uploads — resubmissions, month-end reruns, a double click.
    A fresh scan of the same paper invoice produces different bytes and will not match,
    which is correct: it is a different image and deserves reading again.
    """
    return hashlib.sha256(data).hexdigest()


def get_cached(conn: sqlite3.Connection, sha: str) -> dict | None:
    row = conn.execute("SELECT result FROM extractions WHERE sha256 = ?", (sha,)).fetchone()
    return json.loads(row["result"]) if row else None


def clear_cache(conn: sqlite3.Connection) -> int:
    """Drop every cached extraction so the next run of a file reads it fresh.

    Corrections are left untouched — those are learning, not cache, and survive a reset.
    """
    n = conn.execute("SELECT COUNT(*) c FROM extractions").fetchone()["c"]
    conn.execute("DELETE FROM extractions")
    conn.commit()
    return n


def put_cached(conn: sqlite3.Connection, sha: str, filename: str, result: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO extractions (sha256, filename, result, created_at) "
        "VALUES (?, ?, ?, ?)",
        (sha, filename, json.dumps(result), time.time()),
    )
    conn.commit()


# ----------------------------------------------------- step 9: learn from humans

def record_correction(conn: sqlite3.Connection, sha: str, field: str,
                      was: str | None, now: str, box: list[float] | None) -> None:
    """Store what a reviewer changed, and crucially *where the right answer was*.

    The box is the valuable part. A corrected value teaches us about one invoice; a
    corrected position teaches us about every invoice like it.
    """
    conn.execute(
        "INSERT INTO corrections (sha256, field, was, now, box, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (sha, field, was, now, json.dumps(box) if box else None, time.time()),
    )
    # The stored result must reflect the correction, or the dedup cache would keep
    # serving the value the human just rejected.
    row = conn.execute("SELECT result FROM extractions WHERE sha256 = ?", (sha,)).fetchone()
    if row:
        result = json.loads(row["result"])
        result.update(value=now, confidence=1.0, status="ok", corrected=True)
        if box:
            result["box"] = box
        conn.execute("UPDATE extractions SET result = ? WHERE sha256 = ?",
                     (json.dumps(result), sha))
    conn.commit()


def correction_boxes(conn: sqlite3.Connection, field: str) -> list[list[float]]:
    """Where corrected values actually sat. These feed straight back into the heat map."""
    rows = conn.execute(
        "SELECT box FROM corrections WHERE field = ? AND box IS NOT NULL", (field,)
    ).fetchall()
    return [json.loads(r["box"]) for r in rows]


def stats(conn: sqlite3.Connection) -> dict:
    ex = conn.execute("SELECT COUNT(*) c FROM extractions").fetchone()["c"]
    co = conn.execute("SELECT COUNT(*) c FROM corrections").fetchone()["c"]
    return {"documents": ex, "corrections": co,
            "correction_rate": round(co / ex, 3) if ex else 0.0}
