from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_clawhub_helper_script_is_provider_neutral():
    content = (PROJECT_ROOT / "clawhub" / "scripts" / "evaluate.sh").read_text(encoding="utf-8")

    assert "OPENAI_API_KEY" not in content
    assert "OpenAI API via litellm (only)" not in content
    assert "configured llm provider" in content.lower() or "configured provider" in content.lower()
