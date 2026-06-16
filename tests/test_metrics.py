"""Tests for MetricsEngine."""

import json
import pytest
from pathlib import Path
from agent_token_guard.metrics import MetricsEngine


@pytest.fixture
def metrics(tmp_path):
    return MetricsEngine(root=tmp_path)


def test_record_creates_file(tmp_path):
    m = MetricsEngine(root=tmp_path)
    m.record("save", tokens_before=1000, tokens_after=200)
    assert (tmp_path / ".agent-token-guard" / "metrics" / "usage.jsonl").exists()


def test_record_appends(metrics):
    metrics.record("save", tokens_before=1000, tokens_after=200)
    metrics.record("resume", tokens_after=200)
    data = metrics.report()
    assert len(data["events"]) == 2


def test_tokens_saved_computed(metrics):
    metrics.record("save", tokens_before=5000, tokens_after=300)
    data = metrics.report()
    assert data["events"][0]["tokens_saved"] == 4700


def test_report_aggregation(metrics):
    metrics.record("save", tokens_before=1000, tokens_after=100, files_avoided=5)
    metrics.record("save", tokens_before=2000, tokens_after=150, files_avoided=3)
    metrics.record("resume", tokens_after=150)
    data = metrics.report()
    assert data["total_tokens_saved"] == 2750
    assert data["total_files_avoided"] == 8
    assert data["sessions"] == 3


def test_report_empty(tmp_path):
    m = MetricsEngine(root=tmp_path)
    data = m.report()
    assert data["sessions"] == 0
    assert data["total_tokens_saved"] == 0


def test_summary_text_no_sessions(tmp_path):
    m = MetricsEngine(root=tmp_path)
    text = m.summary_text()
    assert "No sessions" in text


def test_summary_text_with_sessions(metrics):
    metrics.record("save", tokens_before=5000, tokens_after=400)
    text = metrics.summary_text()
    assert "sessions" in text
    assert "tokens saved" in text


def test_clear_wipes_log(metrics):
    metrics.record("save", tokens_before=1000, tokens_after=100)
    metrics.clear()
    data = metrics.report()
    assert data["sessions"] == 0


def test_cost_estimate_positive(metrics):
    metrics.record("save", tokens_before=1_000_000, tokens_after=0)
    data = metrics.report()
    assert data["estimated_cost_saved_usd"] > 0
