"""Codex adapter — generates AGENTS.md and .codex/skills/ files."""

from __future__ import annotations

from pathlib import Path

from .common import remove_file, remove_managed_section, upsert_managed_section, write_file

_AGENTS_MD = """\
# Project Instructions

<!-- Managed by AgentTokenGuard. Edit source files under .agent-token-guard/ -->

## Session Context

At the start of every session, load these files in order:

1. `.agent-token-guard/memory/session.md` — last saved session
2. `.agent-token-guard/memory/repo-summary.md` — project overview
3. `.agent-token-guard/index/file-map.json` — file map (use instead of scanning)

If `session.md` exists, do **not** re-explore the repo.

## Output Rules

- Answer first. Explain only when the reasoning is non-obvious.
- Show only changed code, not full files.
- Use bullets. Skip prose for enumerations.
- No preambles ("Sure!", "Great!"). No trailing summaries.
- Summarize logs. Do not paste raw terminal output.

## File Reading Rules

- Use grep/search — no full-repo scans.
- Read summaries before source files.
- Read `touched_files` from session memory first.
- Confirm before reading files > 100 KB.
- Ignore: `node_modules/`, `dist/`, `build/`, `target/`, `vendor/`, `.venv/`.

## Skills

Load detailed instructions on demand with:

- `#token-guard/save` — save session
- `#token-guard/resume` — load session context
- `#token-guard/report` — token savings report

## Token Savings

This project uses [AgentTokenGuard](https://github.com/your-org/agent-token-guard).
"""

_SKILL_MD = """\
# token-guard

AgentTokenGuard skill for Codex — session memory and token optimisation.

## Commands

### save

Save the current session context.

```bash
atg save \\
  --summary "What was done" \\
  --decisions "Decision A" \\
  --todos "Next task" \\
  --files "src/foo.py" \\
  --next "Start with X next time"
```

### resume

Load compact context at session start.

```bash
atg resume
```

Paste output at the top of the agent session.

### report

Show token savings.

```bash
atg report
```

### index

Build repo summary and file map.

```bash
atg index
```

### compress

Compress verbose output.

```bash
cat output.txt | atg compress
atg compress --file output.txt
```

## Session File Location

`.agent-token-guard/memory/session.md`

## Progressive Loading

This skill loads only what is needed:
- `session.md` is loaded at session start (~150–400 tokens)
- `repo-summary.md` is loaded when asking about the project (~200–600 tokens)
- `file-map.json` is consulted when searching for files (replaces repo scan)
"""


class CodexAdapter:
    """Generate Codex integration files."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()

    def generate(self) -> list[str]:
        """Write all Codex integration files. Returns list of created paths."""
        created: list[str] = []

        agents_md = self.root / "AGENTS.md"
        mode = upsert_managed_section(agents_md, _AGENTS_MD)
        if mode == "created":
            created.append("AGENTS.md")
        elif mode == "appended":
            created.append("AGENTS.md (appended)")
        elif mode == "updated":
            created.append("AGENTS.md (updated)")
        else:
            created.append("AGENTS.md (already configured - skipped)")

        skill_dir = self.root / ".codex" / "skills" / "token-guard"
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_file = skill_dir / "SKILL.md"
        write_file(skill_file, _SKILL_MD)
        created.append(".codex/skills/token-guard/SKILL.md")

        return created

    def uninstall(self) -> list[str]:
        """Remove Codex integration files installed by this adapter."""
        removed: list[str] = []
        agents_md = self.root / "AGENTS.md"
        if remove_managed_section(agents_md):
            removed.append("AGENTS.md (section removed)")

        skill_rel = ".codex/skills/token-guard/SKILL.md"
        if remove_file(self.root / skill_rel):
            removed.append(skill_rel)
        return removed
