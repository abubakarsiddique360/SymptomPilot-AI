"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from symptompilot.config import PROJECT_ROOT, Settings
from symptompilot.runtime import Runtime, build_runtime

KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"


@pytest.fixture(scope="session")
def knowledge_dir() -> Path:
    return KNOWLEDGE_DIR


@pytest.fixture()
def settings(tmp_path: Path, knowledge_dir: Path) -> Settings:
    return Settings(
        embed_backend="none",
        llm_provider="none",
        db_path=tmp_path / "test.db",
        kb_dir=knowledge_dir,
        top_k=3,
    )


@pytest.fixture()
def runtime(settings: Settings) -> Runtime:
    return build_runtime(settings, embedder=None)


@pytest.fixture()
def client(runtime: Runtime):
    from fastapi.testclient import TestClient

    from symptompilot.api import create_app

    with TestClient(create_app(runtime.settings, runtime=runtime)) as test_client:
        yield test_client
