# AgentTokenGuard

**Reduce LLM agent session token waste by 30–70%** through smart session memory, repo indexing, output compression, and usage metrics.

Works with **Claude Code**, **Codex**, **GitHub Copilot**, **Cursor**, and generic **Agent Skills** frameworks.

---

## The Problem

Every agent session starts blank:

- Re-reads 50–200 files to understand the repo
- Re-explains what was already decided last session
- Pastes full stack traces and CI logs into context
- Has no memory of open TODOs or recent decisions

This wastes tokens, costs money, and slows you down.

## The Solution

AgentTokenGuard builds a **controlled context layer**:

```
your-repo/
├── CLAUDE.md                          ← Claude Code entry context
├── AGENTS.md                          ← Codex entry context
└── .agent-token-guard/
    ├── memory/
    │   ├── session.md                 ← compact last-session context
    │   ├── decisions.md               ← key decisions log
    │   ├── todo.md                    ← open tasks
    │   └── repo-summary.md            ← project overview (replaces repo scan)
    ├── index/
    │   ├── file-map.json              ← file structure index
    │   └── dependency-map.json        ← import graph
    ├── rules/
    │   ├── output-policy.md           ← response format rules
    │   └── read-policy.md             ← file reading rules
    └── metrics/
        └── usage.jsonl                ← token savings log
```

Instead of re-scanning the repo every session, the agent reads the summary (~300 tokens) and only reads what it actually needs.

---

## Install

```bash
pip install agent-token-guard
```

Requires Python 3.9+.

---

## Quick Start

```bash
# 1. Initialise in your repo (creates assistant instructions + policy files)
cd my-repo
atg init --agents all

# 2. Build the repo index (creates repo-summary.md and file-map.json)
atg index

# 3. Work in your agent session as normal

# 4. At the end of each session, save context
atg save \
  --summary "Implemented JWT authentication" \
  --decisions "Use RS256, not HS256" "Tokens expire in 1 hour" \
  --todos "Add refresh token endpoint" "Write integration tests" \
  --files "src/auth.py" "src/models/user.py" \
  --next "Start with the refresh token endpoint"

# 5. At the start of the next session, load context
atg resume
```

Paste the `atg resume` output at the top of your agent session. The agent now has full context in ~200–400 tokens instead of 2,000–10,000.

---

## Commands

### `atg init`

Creates all integration files for a repo.

```
atg init [--agents claude,codex,copilot,cursor,agents,all] [--root PATH]
```

Generates:
- `CLAUDE.md` (or appends to existing)
- `AGENTS.md` (or appends to existing)
- `.github/copilot-instructions.md` (or appends to existing)
- `.cursor/rules/agent-token-guard.mdc`
- `.agents/skills/token-guard/SKILL.md`
- `.claude/commands/` — `/save`, `/resume`, `/token-report`, `/compress-output`
- `.codex/skills/token-guard/SKILL.md`
- `.agent-token-guard/rules/` — output and read policies

### `atg uninstall`

Removes installed adapter files and optionally local ATG data.

```
atg uninstall [--agents claude,codex,copilot,cursor,agents,all] [--purge-data]
```

`--purge-data` deletes `.agent-token-guard/` after adapter cleanup.

---

### `atg save`

Saves current session context.

```
atg save \
  --summary "What was done" \
  --decisions "Decision A" "Decision B" \
  --todos "Task 1" "Task 2" \
  --files "src/foo.py" \
  --next "What to do next session"
```

If `--files` is omitted, touched files are auto-detected from `git diff --name-only HEAD`.

If `--summary` is omitted, you are prompted to type one interactively.

---

### `atg resume`

Prints compact session context for pasting at session start.

```
atg resume [--raw]
```

`--raw` outputs plain text (no Rich formatting), suitable for piping or scripting.

---

### `atg index`

Builds the repo summary, file map, and dependency map.

```
atg index [--root PATH]
```

Generates:
- `.agent-token-guard/memory/repo-summary.md`
- `.agent-token-guard/index/file-map.json`
- `.agent-token-guard/index/dependency-map.json`

Re-run after major structural changes to the repo.

---

### `atg compress`

Compresses verbose text: stack traces, CI logs, repeated output.

```
# From a file
atg compress --file output.txt

# From stdin
cat long-output.txt | atg compress

# Write to file
atg compress --file output.txt --output compressed.txt
```

What it does:
- Trims stack traces: keeps first 3 + last 5 frames, replaces middle with a count
- Collapses repeated log lines (e.g. 50 identical `INFO:` lines → 3 + a note)
- Summarizes passing CI sections
- Normalises whitespace

Typical savings: **40–75%** on verbose CI output.

---

### `atg report`

Shows accumulated token savings.

```
atg report [--json]
```

### `atg doctor`

Runs ship-readiness checks for environment and dependencies.

```
atg doctor [--json]
```

Checks:
- Python version
- Required Python modules
- Git binary and git repo status
- `.agent-token-guard/` write permissions

Example output:

```
Token Savings Report
  Sessions recorded       12
  Total tokens saved      284,500
  Files avoided           87
  Estimated cost saved    ~$1.2803 USD
```

---

## Claude Code Integration

After `atg init`, Claude Code gets:

**CLAUDE.md** — instructs the agent to load session memory and follow output/read policies.

**Custom commands** (available as `/save`, `/resume`, `/token-report`, `/compress-output`):

```bash
# In a Claude Code session:
/save
/resume
/token-report
/compress-output
```

These are documentation commands — they show the `atg` CLI invocation to run.

---

## Codex Integration

After `atg init`, Codex gets:

**AGENTS.md** — project instructions with session context loading rules.

**Skill** (`.codex/skills/token-guard/SKILL.md`) — loads only when the `#token-guard` prefix is used, following Codex's progressive-loading pattern.

---

## How Token Savings Work

| Source | Mechanism | Typical savings |
|---|---|---|
| Session memory | Resume compact context instead of re-exploring | 30–60% of session-start tokens |
| Repo summary | Read 300-token summary instead of scanning 100+ files | 50–80% of initial file reads |
| Output policy | Answer-first, diff-only responses | 20–40% of output tokens |
| Log compression | Stack trace + CI output trimming | 40–75% of pasted logs |

Actual savings depend on repo size, session patterns, and how verbose the agent tends to be. Large repos with long sessions see the highest savings.

---

## Development

```bash
git clone <repo>
cd agent-token-optimiser

pip install -e ".[dev]"
pytest
```

### Project Structure

```
src/agent_token_guard/
├── __init__.py
├── cli.py          ← Typer CLI (all atg commands)
├── memory.py       ← MemoryManager (save/resume)
├── indexer.py      ← RepoIndexer (file-map, dep-map, repo-summary)
├── compressor.py   ← OutputCompressor (log/trace trimming + policies)
├── metrics.py      ← MetricsEngine (usage.jsonl + reporting)
└── adapters/
    ├── claude.py   ← CLAUDE.md + .claude/commands/
    ├── codex.py    ← AGENTS.md + .codex/skills/
    ├── platforms.py← Copilot/Cursor/Agent-Skills adapters
    └── common.py   ← managed section helpers for install/uninstall
```

---

## Roadmap

**Phase 1 (current)** — Session memory, repo index, output compression, multi-platform adapters (Claude/Codex/Copilot/Cursor/Agent-Skills), doctor checks, metrics.

**Phase 2** — Git hook integration (`post-commit` auto-save), CI log compression, semantic code index with tree-sitter, team policy templates.

**Phase 3** — Central dashboard, per-project policy management, VS Code extension.

---

## License

MIT
