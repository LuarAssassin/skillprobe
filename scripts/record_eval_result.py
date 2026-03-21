#!/usr/bin/env python3
"""
Record one evaluation result into the evaluations DB.
Reads JSON from file or stdin. Used by the agent after running an in-agent eval.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.store import init_db, upsert_evaluation_result


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
    p = argparse.ArgumentParser(description="Record evaluation result into SQLite")
    p.add_argument("json_file", nargs="?", help="JSON file (default: stdin)")
    p.add_argument("--db", default=None, help="SQLite path (default: skillprobe/outputs/evaluations.db)")
    args = p.parse_args()

    if args.json_file:
        data = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    else:
        data = json.load(sys.stdin)
    data = _normalize_result_for_recording(data)

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
