import os

from click.testing import CliRunner

from apps.cli.main import cli


def test_plan_requires_model_when_runtime_config_is_missing():
    runner = CliRunner()
    env = dict(os.environ)
    env.pop("SKILLPROBE_MODEL", None)
    env.pop("MODEL", None)

    result = runner.invoke(cli, ["plan", "examples/sample-skill"], env=env)

    assert result.exit_code != 0
    assert "model" in result.output.lower()
    assert "SKILLPROBE_MODEL" in result.output


def test_plan_uses_runtime_model_from_environment():
    runner = CliRunner()
    env = dict(os.environ)
    env["SKILLPROBE_MODEL"] = "claude-sonnet-4"

    result = runner.invoke(cli, ["plan", "examples/sample-skill", "--tasks", "6"], env=env)

    assert result.exit_code == 0
    assert '"model": "claude-sonnet-4"' in result.output
