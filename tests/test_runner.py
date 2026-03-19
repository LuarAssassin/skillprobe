from packages.core.eval_spec.models import RunConfig
from packages.generators.task_generator.models import Task
from packages.runners import runner


def test_execute_single_task_passes_configured_tools_to_completion(monkeypatch):
    captured_kwargs = {}

    class _Usage:
        prompt_tokens = 12
        completion_tokens = 8

    class _Message:
        content = "Summary: done\nActions: next"
        tool_calls = []

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]
        usage = _Usage()

    def _fake_completion(**kwargs):
        captured_kwargs.update(kwargs)
        return _Response()

    monkeypatch.setattr(runner, "completion", _fake_completion)

    task = Task(
        task_id="retrieval-001",
        task_type="retrieval",
        prompt="Find recent papers about blood pressure interventions.",
        difficulty="medium",
    )
    config = RunConfig(
        model="test-model",
        temperature=0.0,
        system_prompt="You are a helpful assistant.",
        tools=["web_search"],
        timeout_seconds=30,
        seed=42,
    )

    result = runner._execute_single_task(task, config, config.system_prompt)

    assert "tools" in captured_kwargs
    assert captured_kwargs["tools"][0]["function"]["name"] == "web_search"
    assert result.tokens_input == 12
    assert result.tokens_output == 8
