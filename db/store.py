"""SQLite store for skills and evaluations."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def _get_schema_sql() -> str:
    p = Path(__file__).parent / "schema.sql"
    return p.read_text(encoding="utf-8")


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Create DB and tables; return connection."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_get_schema_sql())
    conn.commit()
    return conn


def insert_skill(
    conn: sqlite3.Connection,
    *,
    id: str,
    name: str,
    slug: str,
    repo_source: str,
    repo_path: str,
    description: str = "",
    profile_json: str | None = None,
    is_directly_testable: bool = True,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO skills
        (id, name, slug, repo_source, repo_path, description, profile_json, is_directly_testable, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (id, name, slug, repo_source, repo_path, description, profile_json, 1 if is_directly_testable else 0),
    )
    conn.commit()


def insert_evaluation(
    conn: sqlite3.Connection,
    *,
    skill_id: str,
    status: str = "pending",
) -> int:
    conn.execute(
        """
        INSERT INTO evaluations (skill_id, status, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(skill_id) DO UPDATE SET status = excluded.status, updated_at = datetime('now')
        """,
        (skill_id, status),
    )
    conn.commit()
    cur = conn.execute("SELECT id FROM evaluations WHERE skill_id = ?", (skill_id,))
    row = cur.fetchone()
    return row[0] if row else 0


def insert_evaluation_tasks(
    conn: sqlite3.Connection,
    evaluation_id: int,
    tasks: list[dict[str, Any]],
) -> None:
    for i, t in enumerate(tasks):
        conn.execute(
            """
            INSERT OR REPLACE INTO evaluation_tasks
            (evaluation_id, task_index, prompt, baseline_output, with_skill_output, baseline_scores_json, with_skill_scores_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                evaluation_id,
                i,
                t.get("prompt", ""),
                t.get("baseline_output"),
                t.get("with_skill_output"),
                json.dumps(t.get("baseline_scores") or {}) if t.get("baseline_scores") else None,
                json.dumps(t.get("with_skill_scores") or {}) if t.get("with_skill_scores") else None,
            ),
        )
    conn.commit()


def upsert_evaluation_result(
    conn: sqlite3.Connection,
    *,
    skill_id: str,
    status: str,
    baseline_total: float | None = None,
    with_skill_total: float | None = None,
    net_gain: float | None = None,
    recommendation_label: str | None = None,
    recommendation_detail: str | None = None,
    report_summary: str | None = None,
    details_json: str | None = None,
    error_message: str | None = None,
    tasks: list[dict[str, Any]] | None = None,
) -> int:
    """Insert or update evaluation and its tasks. Returns evaluation id."""
    conn.execute(
        """
        INSERT INTO evaluations
        (skill_id, status, baseline_total, with_skill_total, net_gain, recommendation_label, recommendation_detail, report_summary, details_json, error_message, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(skill_id) DO UPDATE SET
          status = excluded.status,
          baseline_total = excluded.baseline_total,
          with_skill_total = excluded.with_skill_total,
          net_gain = excluded.net_gain,
          recommendation_label = excluded.recommendation_label,
          recommendation_detail = excluded.recommendation_detail,
          report_summary = excluded.report_summary,
          details_json = excluded.details_json,
          error_message = excluded.error_message,
          updated_at = datetime('now')
        """,
        (
            skill_id,
            status,
            baseline_total,
            with_skill_total,
            net_gain,
            recommendation_label,
            recommendation_detail,
            report_summary,
            details_json,
            error_message,
        ),
    )
    conn.commit()
    cur = conn.execute("SELECT id FROM evaluations WHERE skill_id = ?", (skill_id,))
    row = cur.fetchone()
    eid = row[0] if row else 0
    if eid and tasks:
        conn.execute("DELETE FROM evaluation_tasks WHERE evaluation_id = ?", (eid,))
        insert_evaluation_tasks(conn, eid, tasks)
    return eid


def get_skills_pending_eval(
    conn: sqlite3.Connection,
    repo_source: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return skills that have no completed evaluation or failed."""
    sql = """
        SELECT s.id, s.name, s.slug, s.repo_path, s.description, s.profile_json
        FROM skills s
        LEFT JOIN evaluations e ON e.skill_id = s.id
        WHERE s.repo_source = ? AND s.is_directly_testable = 1
          AND (e.id IS NULL OR e.status NOT IN ('completed', 'running'))
        ORDER BY s.slug
    """
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    cur = conn.execute(sql, (repo_source,))
    rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "name": r[1],
            "slug": r[2],
            "repo_path": r[3],
            "description": (r[4] or "")[:500],
            "profile_json": r[5],
        }
        for r in rows
    ]


def get_all_evaluations(
    conn: sqlite3.Connection,
    repo_source: str,
) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT e.skill_id, s.name, s.slug, e.status, e.baseline_total, e.with_skill_total, e.net_gain, e.recommendation_label, e.updated_at
        FROM evaluations e
        JOIN skills s ON s.id = e.skill_id
        WHERE s.repo_source = ?
        ORDER BY (e.net_gain IS NULL), e.net_gain DESC, s.slug
        """,
        (repo_source,),
    )
    return [
        {
            "skill_id": r[0],
            "name": r[1],
            "slug": r[2],
            "status": r[3],
            "baseline_total": r[4],
            "with_skill_total": r[5],
            "net_gain": r[6],
            "recommendation_label": r[7],
            "updated_at": r[8],
        }
        for r in cur.fetchall()
    ]
