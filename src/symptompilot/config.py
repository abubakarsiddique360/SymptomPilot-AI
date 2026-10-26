"""Runtime configuration.

Everything is optional: the app boots with no environment variables at all and
runs in a fully local, no-LLM mode. Set the ``SYMPTOMPILOT_*`` variables to opt
into a local Ollama model or an OpenAI-compatible endpoint.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
DEFAULT_KB_DIR = PROJECT_ROOT / "knowledge"
DEFAULT_DB_PATH = PROJECT_ROOT / "var" / "symptompilot.db"


def _default_paths() -> tuple[Path, Path]:
    """Locate the corpus and database for source checkouts *and* installed copies."""

    base = PROJECT_ROOT if (PROJECT_ROOT / "knowledge").is_dir() else Path.cwd()
    return base / "knowledge", base / "var" / "symptompilot.db"


PREFIX = "SYMPTOMPILOT_"

DISCLAIMER = (
    "SymptomPilot is an educational triage aid, not a clinician. It cannot diagnose, "
    "rule out, or treat any condition. If you think you are having an emergency, call your "
    "local emergency number immediately."
)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(PREFIX + name, default).strip()


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    llm_provider: str = "auto"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embed_backend: str = "auto"
    embed_model: str = "nomic-embed-text"

    db_path: Path = field(default_factory=lambda: _default_paths()[1])
    kb_dir: Path = field(default_factory=lambda: _default_paths()[0])

    top_k: int = 5
    bm25_weight: float = 0.65
    abstain_threshold: float = 0.15
    min_chunk_score: float = 0.05
    llm_timeout: float = 45.0

    allowed_origins: tuple[str, ...] = (
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    )
    disclaimer: str = DISCLAIMER
    extra: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def from_env(cls) -> Settings:
        origins = _env("ALLOWED_ORIGINS")
        return cls(
            llm_provider=_env("LLM_PROVIDER", "auto").lower(),
            ollama_url=_env("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=_env("OLLAMA_MODEL", "llama3.2"),
            openai_base_url=_env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            openai_api_key=_env("OPENAI_API_KEY"),
            openai_model=_env("OPENAI_MODEL", "gpt-4o-mini"),
            embed_backend=_env("EMBED_BACKEND", "auto").lower(),
            embed_model=_env("EMBED_MODEL", "nomic-embed-text"),
            db_path=Path(_env("DB_PATH") or _default_paths()[1]),
            kb_dir=Path(_env("KB_DIR") or _default_paths()[0]),
            top_k=max(1, min(20, _env_int("TOP_K", 5))),
            bm25_weight=min(1.0, max(0.0, _env_float("BM25_WEIGHT", 0.65))),
            abstain_threshold=_env_float("ABSTAIN_THRESHOLD", 0.15),
            min_chunk_score=_env_float("MIN_CHUNK_SCORE", 0.05),
            llm_timeout=_env_float("LLM_TIMEOUT", 45.0),
            allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()) or cls.allowed_origins,
        )


def get_settings() -> Settings:
    return Settings.from_env()
