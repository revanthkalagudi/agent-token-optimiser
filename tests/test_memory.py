"""Tests for MemoryManager."""

import pytest
from pathlib import Path
from agent_token_guard.memory import MemoryManager


@pytest.fixture
def tmp_root(tmp_path):
    return tmp_path


def test_save_creates_files(tmp_root):
    mm = MemoryManager(root=tmp_root)
    result = mm.save(
        summary="Built the auth module",
        decisions=["Use JWT", "Postgres for sessions"],
        todos=["Write tests", "Add rate limiting"],
        touched_files=["src/auth.py", "src/models.py"],
        next_steps="Start with rate limiting",
    )

    assert (tmp_root / ".agent-token-guard" / "memory" / "session.md").exists()
    assert (tmp_root / ".agent-token-guard" / "memory" / "decisions.md").exists()
    assert (tmp_root / ".agent-token-guard" / "memory" / "todo.md").exists()
    assert result["tokens_compact"] < result["tokens_full"]
    assert result["tokens_compact"] > 0


def test_resume_returns_compact_context(tmp_root):
    mm = MemoryManager(root=tmp_root)
    mm.save(
        summary="Refactored the pipeline",
        decisions=["Drop Celery, use asyncio"],
        todos=["Update docs"],
        next_steps="Update the README",
    )
    context = mm.resume()
    assert "Refactored the pipeline" in context
    assert "Drop Celery" in context
    assert "Update docs" in context
    assert "agent-token-guard" in context


def test_resume_no_session(tmp_root):
    mm = MemoryManager(root=tmp_root)
    result = mm.resume()
    assert "No saved session" in result


def test_roundtrip_preserves_data(tmp_root):
    mm = MemoryManager(root=tmp_root)
    mm.save(
        summary="Added caching layer",
        decisions=["Redis for cache"],
        todos=["Monitor hit rate"],
        touched_files=["src/cache.py"],
        next_steps="Profile cache performance",
    )
    raw = mm.load_raw()
    assert raw["summary"] == "Added caching layer"
    assert "Redis for cache" in raw["decisions"]
    assert "Monitor hit rate" in raw["todos"]


def test_save_empty_lists(tmp_root):
    mm = MemoryManager(root=tmp_root)
    result = mm.save(summary="Quick fix")
    assert result["tokens_compact"] > 0
    assert "Quick fix" in mm.resume()


def test_token_estimate_is_positive(tmp_root):
    mm = MemoryManager(root=tmp_root)
    result = mm.save(summary="x" * 1000)
    assert result["tokens_full"] > 0
    assert result["tokens_compact"] > 0
