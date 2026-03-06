"""
SQLite setup for job state and domain configs.
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "api.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS domains (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                aspects     TEXT NOT NULL,   -- JSON array
                description TEXT,
                is_preset   INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id           TEXT PRIMARY KEY,
                status       TEXT NOT NULL DEFAULT 'queued',
                domain       TEXT NOT NULL,
                method       TEXT NOT NULL,
                aspects      TEXT NOT NULL,  -- JSON array
                total        INTEGER,
                completed    INTEGER NOT NULL DEFAULT 0,
                predictions  TEXT,           -- JSON array when done
                report       TEXT,           -- JSON object when done
                error        TEXT,
                created_at   TEXT NOT NULL,
                completed_at TEXT
            );
        """)
        _seed_presets(conn)


# ── Domain helpers ────────────────────────────────────────────────────────────

PRESETS = [
    {
        "id": "movie",
        "name": "Movie",
        "aspects": ["acting_performances", "story_plot", "pacing", "visuals", "directing", "writing"],
        "description": "A theatrical film or streaming movie",
        "is_preset": True,
    },
    {
        "id": "restaurant",
        "name": "Restaurant",
        "aspects": ["food_quality", "service", "ambiance", "value_for_money", "cleanliness", "menu_variety"],
        "description": "A dining or food service establishment",
        "is_preset": True,
    },
    {
        "id": "software",
        "name": "Software / SaaS",
        "aspects": ["ease_of_use", "performance", "reliability", "customer_support", "features", "value_for_money"],
        "description": "A software product or SaaS application",
        "is_preset": True,
    },
    {
        "id": "hotel",
        "name": "Hotel",
        "aspects": ["room_quality", "cleanliness", "service", "location", "value_for_money", "amenities"],
        "description": "A hotel or accommodation property",
        "is_preset": True,
    },
]


def _seed_presets(conn: sqlite3.Connection) -> None:
    for p in PRESETS:
        conn.execute(
            """
            INSERT OR IGNORE INTO domains (id, name, aspects, description, is_preset)
            VALUES (?, ?, ?, ?, ?)
            """,
            (p["id"], p["name"], json.dumps(p["aspects"]), p["description"], int(p["is_preset"])),
        )


def get_domain(domain_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM domains WHERE id = ?", (domain_id,)).fetchone()
    if row is None:
        return None
    return _row_to_domain(row)


def list_domains() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM domains ORDER BY is_preset DESC, name").fetchall()
    return [_row_to_domain(r) for r in rows]


def insert_domain(domain_id: str, name: str, aspects: list[str], description: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO domains (id, name, aspects, description, is_preset) VALUES (?, ?, ?, ?, 0)",
            (domain_id, name, json.dumps(aspects), description),
        )


def _row_to_domain(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["aspects"] = json.loads(d["aspects"])
    d["is_preset"] = bool(d["is_preset"])
    return d


# ── Job helpers ───────────────────────────────────────────────────────────────

def insert_job(job_id: str, domain: str, method: str, aspects: list[str], total: int, created_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, status, domain, method, aspects, total, created_at)
            VALUES (?, 'queued', ?, ?, ?, ?, ?)
            """,
            (job_id, domain, method, json.dumps(aspects), total, created_at),
        )


def update_job_progress(job_id: str, completed: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status='running', completed=? WHERE id=?",
            (completed, job_id),
        )


def complete_job(job_id: str, predictions: list, report: dict, completed_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status='done', predictions=?, report=?, completed_at=?, completed=total
            WHERE id=?
            """,
            (json.dumps(predictions), json.dumps(report), completed_at, job_id),
        )


def fail_job(job_id: str, error: str, completed_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status='failed', error=?, completed_at=? WHERE id=?",
            (error, completed_at, job_id),
        )


def get_job(job_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    for col in ("aspects", "predictions", "report"):
        if d[col] is not None:
            d[col] = json.loads(d[col])
    return d
