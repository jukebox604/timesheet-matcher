import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path("/workspace/data/timesheet.db")

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                project_id TEXT,
                task_name TEXT,
                project_name TEXT,
                description TEXT,
                date TEXT,
                start_time TEXT,
                end_time TEXT,
                minutes INTEGER,
                billable INTEGER DEFAULT 0,
                status TEXT DEFAULT 'proposed',
                matched INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.0,
                created_at TEXT,
                updated_at TEXT
            )"""
        )
        conn.commit()

def insert_proposal(payload: dict[str, Any]) -> int:
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO proposals
            (task_id, project_id, task_name, project_name, description, date, start_time, end_time, minutes, billable, matched, confidence, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(payload.get("task_id", "")),
                str(payload.get("project_id", "")),
                payload.get("task_name", ""),
                payload.get("project_name", ""),
                payload.get("description", ""),
                payload.get("date", ""),
                payload.get("start_time", ""),
                payload.get("end_time", ""),
                int(payload.get("minutes", 0)),
                int(payload.get("billable", 0)),
                int(payload.get("matched", 0)),
                float(payload.get("confidence", 0.0)),
                payload.get("status", "proposed"),
                now,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)

def fetch_proposals(status: str | None = None) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM proposals ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

def update_proposal_status(proposal_id: int, status: str) -> None:
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute("UPDATE proposals SET status=?, updated_at=? WHERE id=?", (status, now, proposal_id))
        conn.commit()
