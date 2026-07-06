"""Tests for Claude and Codex adapters."""

import pytest
from pathlib import Path
from agent_token_guard.adapters import (
    AgentsAdapter,
    ClaudeAdapter,
    CodexAdapter,
    CopilotAdapter,
    CursorAdapter,
)


@pytest.fixture
def tmp_root(tmp_path):
    return tmp_path


# --- ClaudeAdapter ---


def test_claude_creates_claude_md(tmp_root):
    adapter = ClaudeAdapter(root=tmp_root)
    created = adapter.generate()
    assert (tmp_root / "CLAUDE.md").exists()
    assert any("CLAUDE.md" in c for c in created)


def test_claude_creates_commands(tmp_root):
    adapter = ClaudeAdapter(root=tmp_root)
    adapter.generate()
    cmds_dir = tmp_root / ".claude" / "commands"
    for name in ("save.md", "resume.md", "token-report.md", "compress-output.md"):
        assert (cmds_dir / name).exists(), f"Missing {name}"


def test_claude_md_content(tmp_root):
    adapter = ClaudeAdapter(root=tmp_root)
    adapter.generate()
    text = (tmp_root / "CLAUDE.md").read_text()
    assert "agent-token-guard" in text
    assert "session.md" in text
    assert "Output Rules" in text


def test_claude_does_not_overwrite_if_already_configured(tmp_root):
    existing = "# Existing CLAUDE.md\n\nagent-token-guard is already here.\n"
    (tmp_root / "CLAUDE.md").write_text(existing)
    adapter = ClaudeAdapter(root=tmp_root)
    created = adapter.generate()
    text = (tmp_root / "CLAUDE.md").read_text()
    assert text == existing  # unchanged
    assert "skipped" in created[0]


def test_claude_appends_to_existing_clean_file(tmp_root):
    existing = "# My Project\n\nSome existing docs.\n"
    (tmp_root / "CLAUDE.md").write_text(existing)
    adapter = ClaudeAdapter(root=tmp_root)
    created = adapter.generate()
    text = (tmp_root / "CLAUDE.md").read_text()
    assert "My Project" in text
    assert "agent-token-guard" in text
    assert "appended" in created[0]


# --- CodexAdapter ---


def test_codex_creates_agents_md(tmp_root):
    adapter = CodexAdapter(root=tmp_root)
    created = adapter.generate()
    assert (tmp_root / "AGENTS.md").exists()
    assert any("AGENTS.md" in c for c in created)


def test_codex_creates_skill(tmp_root):
    adapter = CodexAdapter(root=tmp_root)
    adapter.generate()
    skill = tmp_root / ".codex" / "skills" / "token-guard" / "SKILL.md"
    assert skill.exists()
    text = skill.read_text()
    assert "atg save" in text
    assert "atg resume" in text


def test_codex_agents_md_content(tmp_root):
    adapter = CodexAdapter(root=tmp_root)
    adapter.generate()
    text = (tmp_root / "AGENTS.md").read_text()
    assert "agent-token-guard" in text
    assert "session.md" in text


def test_codex_does_not_overwrite_if_configured(tmp_root):
    existing = "# AGENTS\n\nagent-token-guard already here.\n"
    (tmp_root / "AGENTS.md").write_text(existing)
    adapter = CodexAdapter(root=tmp_root)
    created = adapter.generate()
    assert (tmp_root / "AGENTS.md").read_text() == existing
    assert "skipped" in created[0]


def test_copilot_creates_instructions(tmp_root):
    adapter = CopilotAdapter(root=tmp_root)
    created = adapter.generate()
    assert (tmp_root / ".github" / "copilot-instructions.md").exists()
    assert "copilot-instructions" in created[0]


def test_cursor_creates_rule_file(tmp_root):
    adapter = CursorAdapter(root=tmp_root)
    created = adapter.generate()
    assert (tmp_root / ".cursor" / "rules" / "agent-token-guard.mdc").exists()
    assert created == [".cursor/rules/agent-token-guard.mdc"]


def test_agents_creates_skill_file(tmp_root):
    adapter = AgentsAdapter(root=tmp_root)
    created = adapter.generate()
    skill = tmp_root / ".agents" / "skills" / "token-guard" / "SKILL.md"
    assert skill.exists()
    assert "atg doctor" in skill.read_text()
    assert created == [".agents/skills/token-guard/SKILL.md"]


def test_claude_uninstall_removes_section_and_commands(tmp_root):
    adapter = ClaudeAdapter(root=tmp_root)
    adapter.generate()
    removed = adapter.uninstall()
    assert any("CLAUDE.md" in x for x in removed)
    assert not (tmp_root / ".claude" / "commands" / "save.md").exists()


def test_codex_uninstall_removes_section_and_skill(tmp_root):
    adapter = CodexAdapter(root=tmp_root)
    adapter.generate()
    removed = adapter.uninstall()
    assert any("AGENTS.md" in x for x in removed)
    assert not (tmp_root / ".codex" / "skills" / "token-guard" / "SKILL.md").exists()
