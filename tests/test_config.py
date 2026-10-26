from __future__ import annotations

from pathlib import Path

from symptompilot.config import DISCLAIMER, Settings, _default_paths


def test_defaults_are_usable() -> None:
    settings = Settings()
    assert settings.llm_provider == "auto"
    assert settings.embed_backend == "auto"
    assert isinstance(settings.kb_dir, Path)
    assert settings.disclaimer == DISCLAIMER
    assert settings.top_k >= 1


def test_from_env_reads_prefixed_variables(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SYMPTOMPILOT_LLM_PROVIDER", "OLLAMA")
    monkeypatch.setenv("SYMPTOMPILOT_OLLAMA_MODEL", "phi3:mini")
    monkeypatch.setenv("SYMPTOMPILOT_TOP_K", "4")
    monkeypatch.setenv("SYMPTOMPILOT_BM25_WEIGHT", "0.5")
    monkeypatch.setenv("SYMPTOMPILOT_DB_PATH", str(tmp_path / "x.db"))
    settings = Settings.from_env()
    assert settings.llm_provider == "ollama"
    assert settings.ollama_model == "phi3:mini"
    assert settings.top_k == 4
    assert settings.bm25_weight == 0.5
    assert settings.db_path == tmp_path / "x.db"


def test_from_env_clamps_and_ignores_bad_numbers(monkeypatch) -> None:
    monkeypatch.setenv("SYMPTOMPILOT_TOP_K", "999")
    monkeypatch.setenv("SYMPTOMPILOT_BM25_WEIGHT", "not-a-number")
    settings = Settings.from_env()
    assert settings.top_k == 20
    assert settings.bm25_weight == 0.65


def test_from_env_parses_origins(monkeypatch) -> None:
    monkeypatch.setenv("SYMPTOMPILOT_ALLOWED_ORIGINS", "https://a.test, https://b.test ,")
    settings = Settings.from_env()
    assert settings.allowed_origins == ("https://a.test", "https://b.test")


def test_default_paths_returns_paths() -> None:
    kb_dir, db_path = _default_paths()
    assert kb_dir.name == "knowledge"
    assert db_path.name == "symptompilot.db"
    assert "var" in db_path.parts
