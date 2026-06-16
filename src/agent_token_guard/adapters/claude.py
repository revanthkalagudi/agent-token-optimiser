"""Claude Code adapter — generates CLAUDE.md and .claude/commands/ files."""

from __future__ import annotations

from pathlib import Path

_CLAUDE_MD = """\
# Project Memory

<!-- Managed by AgentTokenGuard. Edit the source files under .agent-token-guard/ -->

## Session Context

At the start of every session, read these files **in order** before touching source code:

1. `.agent-token-guard/memory/session.md` — last saved session (summary, decisions, TODOs)
2. `.agent-token-guard/memory/repo-summary.md` — project overview
3. `.agent-token-guard/index/file-map.json` — file structure (use instead of full repo scan)

If `session.md` is present, **do not** re-explore the repo from scratch.

## Output Rules

- Answer first; explain only when the WHY is non-obvious.
- Show only changed code, not full files.
- Use bullets for lists; avoid paragraphs for enumerations.
- Skip log-style updates like "Now I will…" — just do it.
- No trailing "Done!" summaries.

## File Reading Rules

- Use targeted `grep`/search. Do not scan the full repo.
- Read summaries before source files.
- Read `touched_files` from session memory before anything else.
- Ask before reading files > 100 KB.
- Never read: `node_modules/`, `dist/`, `build/`, `target/`, `vendor/`, `.venv/`.

## Commands

- `/save` — save current session to `.agent-token-guard/memory/session.md`
- `/resume` — print compact context for the current session
- `/token-report` — show estimated token savings
- `/compress-output` — compress a block of text (paste below the command)

## Token Savings

This project uses [AgentTokenGuard](https://github.com/your-org/agent-token-guard)
to reduce token waste. Estimated savings: 30–70% depending on repo size and session patterns.
"""

_SAVE_COMMAND = """\
# /save — Save Session Context

Save the current session to `.agent-token-guard/memory/session.md`.

## Usage

Run in your terminal (not inside the agent):

```bash
atg save
```

Or, to provide context inline, run:

```bash
atg save \\
  --summary "What was accomplished this session" \\
  --decisions "Decision 1" "Decision 2" \\
  --todos "Open task 1" "Open task 2" \\
  --files "src/foo.py" "src/bar.py" \\
  --next "What to do next session"
```

## What It Does

- Writes a compact session snapshot to `.agent-token-guard/memory/session.md`
- Updates `decisions.md` and `todo.md`
- Records token savings in `metrics/usage.jsonl`
- Keeps next session context under 500 tokens
"""

_RESUME_COMMAND = """\
# /resume — Resume from Saved Context

Print the compact context block for the current session.

## Usage

```bash
atg resume
```

Paste the output at the start of your next agent session, or reference it with:

> "Load the session context from `.agent-token-guard/memory/session.md`"

## What It Does

- Reads `.agent-token-guard/memory/session.md`
- Returns a compact block: summary, decisions, TODOs, touched files, next steps
- Typically 100–400 tokens (vs 2,000–10,000 for a cold session)
"""

_TOKEN_REPORT_COMMAND = """\
# /token-report — Token Savings Report

Show estimated token savings across sessions.

## Usage

```bash
atg report
```

## Output

- Sessions recorded
- Total tokens saved
- Files avoided
- Estimated cost saved (USD)
"""

_COMPRESS_COMMAND = """\
# /compress-output — Compress Verbose Text

Compress a block of text (stack traces, CI logs, agent output).

## Usage

```bash
# Compress stdin
cat long-output.txt | atg compress

# Compress a file
atg compress --file path/to/output.txt
```

## What It Does

- Trims stack traces to first 3 + last 5 frames
- Collapses repeated log lines
- Summarizes passing CI sections
- Normalizes whitespace

Typical savings: 40–75% on verbose CI output.
"""


class ClaudeAdapter:
    """Generate Claude Code integration files."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()

    def generate(self) -> list[str]:
        """Write all Claude integration files. Returns list of created paths."""
        created: list[str] = []

        claude_md = self.root / "CLAUDE.md"
        if claude_md.exists():
            existing = claude_md.read_text()
            if "agent-token-guard" not in existing:
                # Append our block rather than overwriting
                claude_md.write_text(existing.rstrip() + "\n\n" + _CLAUDE_MD)
                created.append("CLAUDE.md (appended)")
            else:
                created.append("CLAUDE.md (already configured — skipped)")
        else:
            claude_md.write_text(_CLAUDE_MD)
            created.append("CLAUDE.md")

        commands_dir = self.root / ".claude" / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)

        for name, content in [
            ("save.md", _SAVE_COMMAND),
            ("resume.md", _RESUME_COMMAND),
            ("token-report.md", _TOKEN_REPORT_COMMAND),
            ("compress-output.md", _COMPRESS_COMMAND),
        ]:
            path = commands_dir / name
            path.write_text(content)
            created.append(f".claude/commands/{name}")

        return created
