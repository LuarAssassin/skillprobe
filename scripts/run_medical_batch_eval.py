#!/usr/bin/env python3
"""
List pending skills for batch evaluation and optionally record result files.
Use with subagents: output pending as JSON, subagents evaluate and write result JSONs,
then run with --record-dir to ingest all results.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.store import init_db, get_skills_pending_eval, get_all_evaluations, upsert_evaluation_result


REPO_SOURCE = "OpenClaw-Medical-Skills"


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Batch eval: list pending or record results")
    p.add_argument("--db", default=None, help="SQLite path")
    p.add_argument("--list-pending", action="store_true", help="Output pending skills as JSON array")
    p.add_argument("--limit", type=int, default=50, help="Max pending to output (default 50)")
    p.add_argument("--record-dir", metavar="DIR", help="Directory of result JSON files to record")
    p.add_argument("--summary", action="store_true", help="Print evaluation summary from DB")
    p.add_argument("--export", metavar="FILE", help="Export all evaluations to JSON (for web/API)")
    args = p.parse_args()

    db_path = args.db or str(ROOT / "outputs" / "evaluations.db")
    conn = init_db(db_path)

    if args.list_pending:
        pending = get_skills_pending_eval(conn, REPO_SOURCE, limit=args.limit)
        # Include full path for agent: repo path is relative to repo root
        repo_root = Path("/tmp/OpenClaw-Medical-Skills")
        out = []
        for s in pending:
            out.append({
                "skill_id": s["id"],
                "name": s["name"],
                "slug": s["slug"],
                "repo_path": s["repo_path"],
                "skill_path": str(repo_root / s["repo_path"]),
                "description": s["description"][:300] if s["description"] else "",
            })
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        conn.close()
        return

    if args.record_dir:
        record_path = Path(args.record_dir)
        results_to_record = []
        if record_path.is_file() and record_path.suffix == ".json":
            raw = json.loads(record_path.read_text(encoding="utf-8"))
            results_to_record = raw if isinstance(raw, list) else [raw]
        elif record_path.is_dir():
            for f in sorted(record_path.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except Exception as e:
                    print("Skip", f.name, e, file=sys.stderr)
                    continue
                results_to_record.append(data)
        else:
            print("Error: not a directory or .json file:", record_path, file=sys.stderr)
            sys.exit(1)
        count = 0
        for data in results_to_record:
            skill_id = data.get("skill_id")
            if not skill_id:
                continue
            tasks = data.get("tasks") or []
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
            count += 1
        print(f"Recorded {count} evaluations from {record_path}")
        conn.close()
        return

    if args.summary:
        evals = get_all_evaluations(conn, REPO_SOURCE)
        completed = [e for e in evals if e["status"] == "completed"]
        print(f"Total evaluations: {len(evals)} | Completed: {len(completed)}")
        for e in completed[:30]:
            print(f"  {e['slug']}: net_gain={e['net_gain']} recommendation={e['recommendation_label']}")
        conn.close()
        return

    if args.export:
        evals = get_all_evaluations(conn, REPO_SOURCE)
        out_path = Path(args.export)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(evals, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Exported {len(evals)} evaluations to {out_path}")
        conn.close()
        return

    p.print_help()
    conn.close()


if __name__ == "__main__":
    main()
