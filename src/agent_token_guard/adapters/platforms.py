"""Additional platform adapters for broader assistant compatibility."""

from __future__ import annotations

from pathlib import Path

from .common import remove_file, remove_managed_section, upsert_managed_section, write_file

_COPILOT_INSTRUCTIONS = """\
# Copilot Instructions

Use AgentTokenGuard as the project's memory layer.

## Session Start

Read these files first:

1. `.agent-token-guard/memory/session.md`
2. `.agent-token-guard/memory/repo-summary.md`
3. `.agent-token-guard/index/file-map.json`

If session memory exists, do not re-scan the full repository.

## Output And Read Policy

- Use concise answer-first responses.
- Prefer diff-focused changes over full file dumps.
- Read targeted files only; avoid broad scans.
- Ask before opening files larger than 100 KB.
"""

_CURSOR_RULE = """\
---
description: AgentTokenGuard memory and read policies
globs:
alwaysApply: true
---

Use `.agent-token-guard/memory/session.md` before exploring code.
Use `.agent-token-guard/memory/repo-summary.md` and `.agent-token-guard/index/file-map.json` for context.
Avoid full repository scans unless explicitly required.
Provide concise, answer-first responses and include only changed code by default.
"""

_AGENTS_SKILL = """\
# token-guard

Cross-framework Agent Skills entry for AgentTokenGuard.

## Session Start

1. Read `.agent-token-guard/memory/session.md`
2. Read `.agent-token-guard/memory/repo-summary.md`
3. Consult `.agent-token-guard/index/file-map.json`

## Commands

```bash
atg save
atg resume
atg index
atg report
atg doctor
```
"""


class CopilotAdapter:
    """Generate GitHub Copilot instructions integration files."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()

    def generate(self) -> list[str]:
        path = self.root / ".github" / "copilot-instructions.md"
        mode = upsert_managed_section(path, _COPILOT_INSTRUCTIONS)
        if mode == "created":
            return [".github/copilot-instructions.md"]
        if mode == "appended":
            return [".github/copilot-instructions.md (appended)"]
        if mode == "updated":
            return [".github/copilot-instructions.md (updated)"]
        return [".github/copilot-instructions.md (already configured - skipped)"]

    def uninstall(self) -> list[str]:
        path = self.root / ".github" / "copilot-instructions.md"
        if remove_managed_section(path):
            return [".github/copilot-instructions.md (section removed)"]
        return []


class CursorAdapter:
    """Generate Cursor rule files."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()

    def generate(self) -> list[str]:
        rel = ".cursor/rules/agent-token-guard.mdc"
        write_file(self.root / rel, _CURSOR_RULE)
        return [rel]

    def uninstall(self) -> list[str]:
        rel = ".cursor/rules/agent-token-guard.mdc"
        if remove_file(self.root / rel):
            return [rel]
        return []


class AgentsAdapter:
    """Generate generic Agent Skills files for multi-framework support."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()

    def generate(self) -> list[str]:
        rel = ".agents/skills/token-guard/SKILL.md"
        write_file(self.root / rel, _AGENTS_SKILL)
        return [rel]

    def uninstall(self) -> list[str]:
        rel = ".agents/skills/token-guard/SKILL.md"
        if remove_file(self.root / rel):
            return [rel]
        return []