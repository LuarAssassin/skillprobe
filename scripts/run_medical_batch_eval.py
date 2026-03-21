#!/usr/bin/env python3
"""
List pending skills for batch evaluation and optionally record result files.
Use with subagents: output pending as JSON, subagents evaluate and write result JSONs,
then run with --record-dir to ingest all results.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.store import init_db, get_skills_pending_eval, get_all_evaluations, upsert_evaluation_result


REPO_SOURCE = "OpenClaw-Medical-Skills"


_SIMULATION_PATTERNS = (
    r"假设",
    r"模拟",
    r"推测",
    r"hypothetical",
    r"simulat",
)

_SELF_EXECUTION_PATTERNS = (
    r"作为编排者.{0,20}(回答|执行|完成)",
    r"我(直接|自己)(回答|执行|完成)",
    r"orchestrator.{0,20}(answer|execut)",
    r"I.{0,5}(will|shall).{0,10}(answer|execute).{0,10}(task|myself)",
)


def _extract_session_id(evidence: object) -> str:
    if isinstance(evidence, dict):
        session_id = evidence.get("session_id")
        return str(session_id).strip() if session_id is not None else ""
    if evidence is None:
        return ""
    return str(evidence).strip()


def _check_dispatch_evidence(data: dict) -> list[str]:
    """Validate dispatch_evidence to ensure orchestrator delegated execution."""
    reasons: list[str] = []
    dispatch = data.get("dispatch_evidence")
    if dispatch is None:
        reasons.append("missing dispatch_evidence field (required to prove orchestrator delegated execution)")
        return reasons

    if not isinstance(dispatch, dict):
        reasons.append("dispatch_evidence must be a dict")
        return reasons

    role = str(dispatch.get("orchestrator_role", "")).strip()
    if role != "prepare_and_score_only":
        reasons.append(
            f"dispatch_evidence.orchestrator_role must be 'prepare_and_score_only', got '{role}'"
        )

    baseline_sid = str(dispatch.get("baseline_agent_session_id", "")).strip()
    skill_sid = str(dispatch.get("skill_agent_session_id", "")).strip()
    if not baseline_sid or not skill_sid:
        reasons.append("dispatch_evidence missing baseline_agent_session_id or skill_agent_session_id")
    elif baseline_sid == skill_sid:
        reasons.append("dispatch_evidence: baseline and skill agent share the same session_id")

    if dispatch.get("baseline_prompt_contains_skill") is True:
        reasons.append("dispatch_evidence: baseline_prompt_contains_skill must be false")

    return reasons


def _check_self_execution(tasks: list[dict]) -> list[int]:
    """Detect patterns suggesting the orchestrator executed tasks itself."""
    flagged: list[int] = []
    for index, task in enumerate(tasks):
        merged = ""
        for field in ("baseline_output", "with_skill_output"):
            merged += str(task.get(field, "")) + "\n"
        merged_lower = merged.lower()
        if any(re.search(p, merged_lower) for p in _SELF_EXECUTION_PATTERNS):
            flagged.append(index)
    return flagged


def _normalize_result_for_recording(data: dict) -> dict:
    """Guardrail: completed results must come from real A/B outputs with dispatch evidence."""
    normalized = dict(data)
    status = str(normalized.get("status", "completed")).lower()
    tasks = normalized.get("tasks") or []

    if status != "completed":
        return normalized

    if not tasks:
        normalized["status"] = "failed"
        normalized["error_message"] = "No task outputs provided; cannot validate real A/B execution."
        return normalized

    reasons: list[str] = []

    dispatch_reasons = _check_dispatch_evidence(normalized)
    reasons.extend(dispatch_reasons)

    incomplete_tasks = []
    missing_evidence_tasks = []
    shared_context_tasks = []
    simulated_tasks = []
    for index, task in enumerate(tasks):
        baseline_output = str(task.get("baseline_output", "")).strip()
        skill_output = str(task.get("with_skill_output", "")).strip()

        if not baseline_output or not skill_output:
            incomplete_tasks.append(index)
            continue

        baseline_session_id = _extract_session_id(task.get("baseline_evidence"))
        with_skill_session_id = _extract_session_id(task.get("with_skill_evidence"))
        if not baseline_session_id or not with_skill_session_id:
            missing_evidence_tasks.append(index)
        elif baseline_session_id == with_skill_session_id:
            shared_context_tasks.append(index)

        merged = f"{baseline_output}\n{skill_output}".lower()
        if any(re.search(pattern, merged, re.IGNORECASE) for pattern in _SIMULATION_PATTERNS):
            simulated_tasks.append(index)

    self_exec_tasks = _check_self_execution(tasks)

    if incomplete_tasks:
        reasons.append(f"missing baseline/with_skill outputs at task indexes: {incomplete_tasks}")
    if missing_evidence_tasks:
        reasons.append(f"missing baseline/with_skill evidence session_id at task indexes: {missing_evidence_tasks}")
    if shared_context_tasks:
        reasons.append(f"baseline and with_skill share the same session_id at task indexes: {shared_context_tasks}")
    if simulated_tasks:
        reasons.append(f"simulated/hypothetical wording detected at task indexes: {simulated_tasks}")
    if self_exec_tasks:
        reasons.append(f"orchestrator self-execution pattern detected at task indexes: {self_exec_tasks}")

    if reasons:
        normalized["status"] = "failed"
        normalized["error_message"] = (
            "Result rejected by strict A/B guardrail: " + "; ".join(reasons)
        )

    return normalized


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
            data = _normalize_result_for_recording(data)
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
