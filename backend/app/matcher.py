from typing import Any
import sqlite3
from difflib import SequenceMatcher
from pathlib import Path

from app.models import insert_proposal
from app.teamwork import get_teamwork_settings, TeamworkClient

DB_PATH = Path("/workspace/data/timesheet.db")
MIN_CONFIDENCE = 0.55


def _score(a: str, b: str) -> float:
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _pick_task(task: dict[str, Any]) -> dict[str, Any]:
    entity = task.get("entity") or {}
    return {
        "id": str(entity.get("id", "")),
        "type": entity.get("type", ""),
        "matchingData": {
            "name": (entity.get("name") or "")
        }
    }


def _best_match(task: dict[str, Any], description: str) -> tuple[dict[str, Any], float]:
    top_task: dict[str, Any] = {}
    top_score: float = 0.0
    for embed in task.get("embeds") or []:
        cand = embed.get("task") or {}
        name = (cand.get("name") or "")
        score = _score(description, name)
        if score > top_score:
            top_score = score
            top_task = {
                "id": str(cand.get("id", "")),
                "type": cand.get("type", ""),
                "matchingData": {"name": name},
            }
    return top_task, top_score


def match_and_propose(description: str, date: str, minutes: int, start_time: str = "", end_time: str = "") -> dict[str, Any] | None:
    client = TeamworkClient()
    payload = _fetch_tasks(client)
    tasks = payload.get("tasks", [])
    best_task: dict[str, Any] = {}
    best_score: float = 0.0
    for task in tasks:
        matched, score = _best_match(task, description)
        if matched and score > best_score:
            best_score = score
            best_task = matched
    if best_score < MIN_CONFIDENCE or not best_task:
        return None
    project_id = _infer_project_id(task, best_task)
    return {
        "task_id": best_task.get("id"),
        "project_id": project_id,
        "task_name": (best_task.get("matchingData") or {}).get("name", ""),
        "project_name": "<project>",
        "description": description,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "minutes": minutes,
        "matched": 1,
        "confidence": round(best_score, 4),
    }


def _infer_project_id(task: dict[str, Any], matched_task: dict[str, Any]) -> str:
    # Prefer the main project identity, otherwise fall back to an empty string.
    # Teamwork sometimes embeds parent task/project data; this is a safe default.
    return str(task.get("tasklist", {}).get("projectId") or "")

