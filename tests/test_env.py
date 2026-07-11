import os

from ai_investor.core.env import load_env


def test_loads_keys_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_GROQ_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "# comment\nTEST_GROQ_KEY=abc123\nQUOTED='hello'\n\nbadline\n")
    load_env(tmp_path)
    assert os.environ["TEST_GROQ_KEY"] == "abc123"
    assert os.environ["QUOTED"] == "hello"
    monkeypatch.delenv("QUOTED", raising=False)


def test_real_environment_wins_over_file(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_GROQ_KEY", "from-shell")
    (tmp_path / ".env").write_text("TEST_GROQ_KEY=from-file\n")
    load_env(tmp_path)
    assert os.environ["TEST_GROQ_KEY"] == "from-shell"


def test_missing_env_file_is_fine(tmp_path):
    load_env(tmp_path)  # no .env present — should not raise
