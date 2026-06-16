"""Tests for RepoIndexer."""

import json
import pytest
from pathlib import Path
from agent_token_guard.indexer import RepoIndexer


@pytest.fixture
def fake_repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("import os\nimport sys\n\ndef main(): pass\n")
    (tmp_path / "src" / "utils.py").write_text("from src.models import User\n")
    (tmp_path / "src" / "models.py").write_text("class User: pass\n")
    (tmp_path / "README.md").write_text("# My Project\n")
    (tmp_path / "pyproject.toml").write_text("[build-system]\n")
    # Large file
    (tmp_path / "src" / "big.py").write_text("x = 1\n" * 20000)
    # Should be ignored
    node_modules = tmp_path / "node_modules" / "lodash"
    node_modules.mkdir(parents=True)
    (node_modules / "index.js").write_text("module.exports = {}")
    return tmp_path


def test_index_creates_files(fake_repo):
    indexer = RepoIndexer(root=fake_repo)
    stats = indexer.index()

    assert (fake_repo / ".agent-token-guard" / "index" / "file-map.json").exists()
    assert (fake_repo / ".agent-token-guard" / "index" / "dependency-map.json").exists()
    assert (fake_repo / ".agent-token-guard" / "memory" / "repo-summary.md").exists()


def test_file_map_excludes_node_modules(fake_repo):
    indexer = RepoIndexer(root=fake_repo)
    indexer.index()

    file_map = json.loads(
        (fake_repo / ".agent-token-guard" / "index" / "file-map.json").read_text()
    )
    keys = list(file_map.keys())
    assert not any("node_modules" in k for k in keys)


def test_large_file_flagged(fake_repo):
    indexer = RepoIndexer(root=fake_repo)
    indexer.index()

    file_map = json.loads(
        (fake_repo / ".agent-token-guard" / "index" / "file-map.json").read_text()
    )
    big_entry = file_map.get("src/big.py")
    assert big_entry is not None
    assert big_entry["large"] is True


def test_entry_points_detected(fake_repo):
    indexer = RepoIndexer(root=fake_repo)
    stats = indexer.index()
    assert "src/main.py" in stats["entry_points"]


def test_dependency_map_python(fake_repo):
    indexer = RepoIndexer(root=fake_repo)
    indexer.index()

    dep_map = json.loads(
        (fake_repo / ".agent-token-guard" / "index" / "dependency-map.json").read_text()
    )
    assert "src/main.py" in dep_map
    assert "os" in dep_map["src/main.py"]


def test_repo_summary_text_fallback(fake_repo):
    indexer = RepoIndexer(root=fake_repo)
    text = indexer.get_repo_summary_text()
    assert "No repo summary" in text

    indexer.index()
    text = indexer.get_repo_summary_text()
    assert "Primary language" in text


def test_stats_counts(fake_repo):
    indexer = RepoIndexer(root=fake_repo)
    stats = indexer.index()
    assert stats["total_files"] >= 5
    assert stats["code_files"] >= 4
    assert stats["large_files"] >= 1
