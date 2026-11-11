"""SQLite helpers and schema initialisation."""
import sqlite3
from datetime import datetime, timezone
from .config import DB_PATH


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetchall(sql: str, args=()) -> list[sqlite3.Row]:
    with conn() as c:
        return c.execute(sql, args).fetchall()


def fetchone(sql: str, args=()) -> sqlite3.Row | None:
    with conn() as c:
        return c.execute(sql, args).fetchone()


def execute(sql: str, args=()) -> int:
    """Execute a write statement and return lastrowid."""
    with conn() as c:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid


def executemany(sql: str, rows: list) -> None:
    with conn() as c:
        c.executemany(sql, rows)
        c.commit()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(
    id          INTEGER PRIMARY KEY,
    name        TEXT,
    url         TEXT,
    department  TEXT,
    kind        TEXT,          -- 'sample' | 'live'
    interval_min INTEGER DEFAULT 60,
    enabled     INTEGER DEFAULT 1,
    last_check  TEXT,
    last_status TEXT
);

CREATE TABLE IF NOT EXISTS documents(
    id          INTEGER PRIMARY KEY,
    source_id   INTEGER,
    url         TEXT,
    title       TEXT,
    gr_number   TEXT,
    gr_date     TEXT,
    doc_type    TEXT,
    scheme      TEXT,
    department  TEXT,
    file_path   TEXT,
    sha256      TEXT UNIQUE,
    detected_at TEXT,
    live_at     TEXT,
    status      TEXT DEFAULT 'new',  -- new | review | live | rejected
    ocr_used    INTEGER DEFAULT 0,
    confidence  REAL,
    summary_mr  TEXT,
    summary_en  TEXT
);

CREATE TABLE IF NOT EXISTS pages(
    id          INTEGER PRIMARY KEY,
    document_id INTEGER,
    page_no     INTEGER,
    text        TEXT
);

CREATE TABLE IF NOT EXISTS chunks(
    id          INTEGER PRIMARY KEY,
    document_id INTEGER,
    page_no     INTEGER,
    text        TEXT,
    embedding   BLOB
);

CREATE TABLE IF NOT EXISTS rules(
    id              INTEGER PRIMARY KEY,
    document_id     INTEGER,
    scheme          TEXT,
    field           TEXT,
    value           TEXT,
    unit            TEXT,
    condition_text  TEXT,
    source_quote    TEXT,
    page_no         INTEGER,
    effective_from  TEXT,
    grounded        INTEGER,
    status          TEXT DEFAULT 'draft'  -- draft | approved | rejected
);

CREATE TABLE IF NOT EXISTS refs(
    id          INTEGER PRIMARY KEY,
    document_id INTEGER,
    ref_gr_number TEXT,
    ref_gr_date   TEXT,
    relation    TEXT   -- replaces | amends | extends | clarifies | refers
);

CREATE TABLE IF NOT EXISTS review_queue(
    id          INTEGER PRIMARY KEY,
    document_id INTEGER,
    reason      TEXT,
    status      TEXT DEFAULT 'pending',  -- pending | approved | rejected
    decided_by  TEXT,
    decided_at  TEXT,
    run_id      INTEGER
);

CREATE TABLE IF NOT EXISTS pipeline_runs(
    id          INTEGER PRIMARY KEY,
    started_at  TEXT,
    finished_at TEXT,
    mode        TEXT,
    new_docs    INTEGER DEFAULT 0,
    status      TEXT   -- running | done | awaiting_review | failed
);

CREATE TABLE IF NOT EXISTS pipeline_events(
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER,
    ts          TEXT,
    document_id INTEGER,
    stage       TEXT,
    status      TEXT,
    message     TEXT
);

CREATE TABLE IF NOT EXISTS queries(
    id              INTEGER PRIMARY KEY,
    ts              TEXT,
    username        TEXT,
    lang            TEXT,
    question_masked TEXT,
    answer          TEXT,
    cited           TEXT,
    refused         INTEGER,
    confidence      REAL,
    latency_ms      INTEGER,
    feedback        INTEGER   -- NULL | 1 (up) | -1 (down)
);

CREATE TABLE IF NOT EXISTS notifications(
    id      INTEGER PRIMARY KEY,
    ts      TEXT,
    kind    TEXT,
    message TEXT,
    read    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_log(
    id      INTEGER PRIMARY KEY,
    ts      TEXT,
    actor   TEXT,
    action  TEXT,
    detail  TEXT
);

CREATE TABLE IF NOT EXISTS eval_runs(
    id          INTEGER PRIMARY KEY,
    ts          TEXT,
    total       INTEGER,
    passed      INTEGER,
    citation_ok INTEGER
);

CREATE TABLE IF NOT EXISTS eval_results(
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER,
    qid         TEXT,
    question    TEXT,
    answer      TEXT,
    refused     INTEGER,
    citation_ok INTEGER,
    answer_ok   INTEGER,
    note        TEXT
);
"""


def init():
    """Create all tables (idempotent)."""
    with conn() as c:
        c.executescript(SCHEMA)
        c.commit()
    _seed_sources()


def _seed_sources():
    """Insert the default sample source if it doesn't exist."""
    from .config import DEPARTMENT as _DEPT  # local import to avoid circular at module level
    existing = fetchone("SELECT id FROM sources WHERE kind='sample'")
    if existing:
        return
    execute(
        """INSERT INTO sources(name, url, department, kind, interval_min, enabled)
           VALUES (?,?,?,?,?,?)""",
        (
            "WCD GR listing (prepared sample)",
            "http://localhost:8000/mock-portal/wcd/",
            _DEPT,
            "sample",
            60,
            1,
        ),
    )


# Run init on import so the DB is always ready
init()
