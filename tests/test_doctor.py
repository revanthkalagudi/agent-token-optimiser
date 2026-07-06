"""Tests for Doctor environment diagnostics."""

from __future__ import annotations

from agent_token_guard.doctor import Doctor


def test_doctor_report_shape(tmp_path):
    report = Doctor(root=tmp_path).run()
    assert "passed" in report
    assert "failed" in report
    assert "checks" in report
    assert isinstance(report["checks"], list)


def test_doctor_has_expected_checks(tmp_path):
    report = Doctor(root=tmp_path).run()
    names = {c["name"] for c in report["checks"]}
    assert "python-version" in names
    assert "python-modules" in names
    assert "git-binary" in names
    assert "git-repo" in names
    assert "guard-dir" in names


def test_guard_dir_is_created_if_missing(tmp_path):
    guard_dir = tmp_path / ".agent-token-guard"
    assert not guard_dir.exists()
    Doctor(root=tmp_path).run()
    assert guard_dir.exists()