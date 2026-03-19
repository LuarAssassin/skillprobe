#!/usr/bin/env python3
"""
Record one evaluation result into the evaluations DB.
Reads JSON from file or stdin. Used by the agent after running an in-agent eval.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.store import init_db, upsert_evaluation_result


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Record evaluation result into SQLite")
    p.add_argument("json_file", nargs="?", help="JSON file (default: stdin)")
    p.add_argument("--db", default=None, help="SQLite path (default: skillprobe/outputs/evaluations.db)")
    args = p.parse_args()

    if args.json_file:
        data = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    else:
        data = json.load(sys.stdin)

    db_path = args.db or str(ROOT / "outputs" / "evaluations.db")
    conn = init_db(db_path)

    skill_id = data.get("skill_id")
    if not skill_id:
        print("Error: missing skill_id", file=sys.stderr)
        sys.exit(1)

    tasks = data.get("tasks") or []
    for t in tasks:
        if isinstance(t.get("baseline_scores"), dict):
            t["baseline_scores"] = t["baseline_scores"]
        if isinstance(t.get("with_skill_scores"), dict):
            t["with_skill_scores"] = t["with_skill_scores"]

    upsert_evaluation_result(
        conn,
        skill_id=skill_id,
        status=data.get("status", "completed"),
        baseline_total=data.get("baseline_total"),
        with_skill_total=data.get("with_skill_total"),
        net_gain=data.get("net_gain"),
        recommendation_label=data.get("recommendation_label"),
        recommendation_detail=data.get("recommendation_detail"),
        report_summary=data.get("report_summary"),
        details_json=json.dumps(data.get("details") or {}, ensure_ascii=False) if data.get("details") else None,
        error_message=data.get("error_message"),
        tasks=tasks,
    )
    conn.close()
    print("Recorded evaluation for skill_id:", skill_id)


if __name__ == "__main__":
    main()
