import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

_VALID_DISPATCH_EVIDENCE = {
    "orchestrator_role": "prepare_and_score_only",
    "baseline_agent_session_id": "arm-a-session",
    "skill_agent_session_id": "arm-b-session",
    "baseline_prompt_contains_skill": False,
}


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_completed_result(**overrides) -> dict:
    """Build a minimal valid completed result, with optional overrides."""
    base = {
        "skill_id": "abc123",
        "status": "completed",
        "dispatch_evidence": dict(_VALID_DISPATCH_EVIDENCE),
        "tasks": [
            {
                "prompt": "task-1",
                "baseline_output": "baseline answer here",
                "with_skill_output": "with-skill answer here",
                "baseline_evidence": {"session_id": "arm-a-session"},
                "with_skill_evidence": {"session_id": "arm-b-session"},
            }
        ],
    }
    base.update(overrides)
    return base


def _get_batch_normalize():
    module = _load_module(
        "run_medical_batch_eval",
        PROJECT_ROOT / "scripts" / "run_medical_batch_eval.py",
    )
    return module._normalize_result_for_recording


def _get_record_normalize():
    module = _load_module(
        "record_eval_result",
        PROJECT_ROOT / "scripts" / "record_eval_result.py",
    )
    return module._normalize_result_for_recording


# --- Existing guardrails (backward compat) ---


def test_batch_recording_guardrail_rejects_missing_outputs():
    normalize = _get_batch_normalize()
    result = normalize(_make_completed_result(
        tasks=[{"prompt": "task-1", "baseline_output": "", "with_skill_output": "answer"}],
    ))
    assert result["status"] == "failed"
    assert "missing baseline/with_skill outputs" in result["error_message"]


def test_batch_recording_guardrail_rejects_simulated_wording():
    normalize = _get_record_normalize()
    result = normalize(_make_completed_result(
        tasks=[
            {
                "prompt": "task-1",
                "baseline_output": "在假设未加载技能的前提下，我会这样回答。",
                "with_skill_output": "在假设加载技能的前提下，我会这样回答。",
                "baseline_evidence": {"session_id": "arm-a"},
                "with_skill_evidence": {"session_id": "arm-b"},
            }
        ],
    ))
    assert result["status"] == "failed"
    assert "simulated/hypothetical wording" in result["error_message"]


def test_batch_recording_guardrail_rejects_missing_evidence():
    normalize = _get_batch_normalize()
    result = normalize(_make_completed_result(
        tasks=[
            {
                "prompt": "task-1",
                "baseline_output": "baseline output",
                "with_skill_output": "with-skill output",
            }
        ],
    ))
    assert result["status"] == "failed"
    assert "missing baseline/with_skill evidence session_id" in result["error_message"]


def test_batch_recording_guardrail_rejects_shared_session_context():
    normalize = _get_batch_normalize()
    result = normalize(_make_completed_result(
        tasks=[
            {
                "prompt": "task-1",
                "baseline_output": "baseline output",
                "with_skill_output": "with-skill output",
                "baseline_evidence": {"session_id": "same-session"},
                "with_skill_evidence": {"session_id": "same-session"},
            }
        ],
    ))
    assert result["status"] == "failed"
    assert "share the same session_id" in result["error_message"]


def test_batch_recording_guardrail_allows_real_outputs_with_distinct_sessions():
    normalize = _get_batch_normalize()
    result = normalize(_make_completed_result())
    assert result["status"] == "completed"


# --- New guardrails: dispatch_evidence ---


def test_rejects_missing_dispatch_evidence():
    normalize = _get_batch_normalize()
    data = _make_completed_result()
    del data["dispatch_evidence"]
    result = normalize(data)
    assert result["status"] == "failed"
    assert "missing dispatch_evidence" in result["error_message"]


def test_rejects_wrong_orchestrator_role():
    normalize = _get_record_normalize()
    data = _make_completed_result()
    data["dispatch_evidence"]["orchestrator_role"] = "executed_tasks_myself"
    result = normalize(data)
    assert result["status"] == "failed"
    assert "orchestrator_role must be 'prepare_and_score_only'" in result["error_message"]


def test_rejects_dispatch_evidence_same_session():
    normalize = _get_batch_normalize()
    data = _make_completed_result()
    data["dispatch_evidence"]["baseline_agent_session_id"] = "same"
    data["dispatch_evidence"]["skill_agent_session_id"] = "same"
    result = normalize(data)
    assert result["status"] == "failed"
    assert "baseline and skill agent share the same session_id" in result["error_message"]


def test_rejects_dispatch_evidence_missing_session_ids():
    normalize = _get_record_normalize()
    data = _make_completed_result()
    data["dispatch_evidence"]["baseline_agent_session_id"] = ""
    result = normalize(data)
    assert result["status"] == "failed"
    assert "missing baseline_agent_session_id or skill_agent_session_id" in result["error_message"]


def test_rejects_baseline_prompt_contains_skill_true():
    normalize = _get_batch_normalize()
    data = _make_completed_result()
    data["dispatch_evidence"]["baseline_prompt_contains_skill"] = True
    result = normalize(data)
    assert result["status"] == "failed"
    assert "baseline_prompt_contains_skill must be false" in result["error_message"]


# --- New guardrails: self-execution detection ---


def test_rejects_orchestrator_self_execution_chinese():
    normalize = _get_batch_normalize()
    data = _make_completed_result(
        tasks=[
            {
                "prompt": "task-1",
                "baseline_output": "作为编排者我直接回答这个问题：答案是X",
                "with_skill_output": "with-skill output here",
                "baseline_evidence": {"session_id": "arm-a"},
                "with_skill_evidence": {"session_id": "arm-b"},
            }
        ],
    )
    result = normalize(data)
    assert result["status"] == "failed"
    assert "self-execution pattern" in result["error_message"]


def test_rejects_orchestrator_self_execution_english():
    normalize = _get_record_normalize()
    data = _make_completed_result(
        tasks=[
            {
                "prompt": "task-1",
                "baseline_output": "I will answer this task myself as orchestrator executing the task",
                "with_skill_output": "with-skill output here",
                "baseline_evidence": {"session_id": "arm-a"},
                "with_skill_evidence": {"session_id": "arm-b"},
            }
        ],
    )
    result = normalize(data)
    assert result["status"] == "failed"
    assert "self-execution pattern" in result["error_message"]


def test_rejects_direct_self_execution_chinese():
    normalize = _get_batch_normalize()
    data = _make_completed_result(
        tasks=[
            {
                "prompt": "task-1",
                "baseline_output": "我直接回答这个医学问题",
                "with_skill_output": "with-skill output",
                "baseline_evidence": {"session_id": "arm-a"},
                "with_skill_evidence": {"session_id": "arm-b"},
            }
        ],
    )
    result = normalize(data)
    assert result["status"] == "failed"
    assert "self-execution pattern" in result["error_message"]


# --- Combined: valid result with all fields ---


def test_full_valid_result_passes_all_guardrails():
    for normalize in (_get_batch_normalize(), _get_record_normalize()):
        result = normalize(_make_completed_result())
        assert result["status"] == "completed", f"Expected completed, got: {result.get('error_message')}"


def test_non_completed_status_skips_guardrails():
    for normalize in (_get_batch_normalize(), _get_record_normalize()):
        data = {"skill_id": "x", "status": "failed", "error_message": "cannot eval"}
        result = normalize(data)
        assert result["status"] == "failed"
        assert result["error_message"] == "cannot eval"
