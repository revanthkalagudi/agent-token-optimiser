"""Output compressor — trim stack traces, CI logs, and verbose agent responses."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_GUARD_DIR = ".agent-token-guard"
_RULES_DIR = f"{_GUARD_DIR}/rules"

_OUTPUT_POLICY = """\
# Output Policy

These rules apply to all agent responses in this project.

## Response Format

- **Answer first.** State the result or decision before any explanation.
- Use bullet points, not paragraphs, for lists of changes or steps.
- Show **only changed code**, never full files unless asked.
- Prefer unified diff format (`--- a/file`, `+++ b/file`) for code changes.
- Summarize logs; do not paste raw output unless the user asks.
- Skip preambles like "Sure!", "Great question!", "Of course!".
- Skip trailing summaries — the user can read the diff.

## File Reading

- Do **not** scan the full repo. Use targeted search (`grep`, `find`, symbol lookup).
- Read `repo-summary.md` and `file-map.json` before reading source files.
- Read changed files first (`git diff --name-only HEAD`).
- Ask before reading files larger than 100 KB.
- Ignore: `node_modules/`, `dist/`, `build/`, `target/`, `vendor/`, `.venv/`.

## Session Start

- Load `.agent-token-guard/memory/session.md` if it exists — skip re-exploring.
- Load `.agent-token-guard/memory/repo-summary.md` for project overview.
- Do **not** re-read files already discussed in session memory.

## Verbosity

- One short sentence per update while working.
- No multi-paragraph docstrings or comment blocks.
- Explanations only when the WHY is non-obvious.
"""

_READ_POLICY = """\
# Read Policy

Rules for deciding which files to read and when.

## Priority Order

1. `.agent-token-guard/memory/session.md` — recent session context
2. `.agent-token-guard/memory/repo-summary.md` — repo overview
3. `.agent-token-guard/index/file-map.json` — file structure
4. Files listed in `touched_files` from session memory
5. Entry points (main.py, app.py, index.ts, etc.)
6. Only then: other source files, on demand

## Never Read Without a Reason

- No speculative full-repo scans.
- No reading files just to "understand the project" — use the summary.
- If the task doesn't require a file, don't read it.

## Large File Guard

Files > 100 KB: confirm with the user before reading.
Files in `large_files` list in repo-summary: read only specific sections.
"""


class OutputCompressor:
    """Compress verbose text (logs, traces, CI output) and generate policy files."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()
        self.rules_dir = self.root / _RULES_DIR
        self.rules_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_policies(self) -> None:
        """Write output-policy.md and read-policy.md to the rules dir."""
        (self.rules_dir / "output-policy.md").write_text(_OUTPUT_POLICY)
        (self.rules_dir / "read-policy.md").write_text(_READ_POLICY)

    def compress(self, text: str) -> tuple[str, dict[str, Any]]:
        """
        Compress a block of text. Returns (compressed_text, stats).

        Applies in order:
        1. Stack trace trimming (keep first + last N frames)
        2. Log deduplication (collapse repeated lines)
        3. CI output summarization
        4. Whitespace normalization
        """
        original_len = len(text)
        original_tokens = self._estimate_tokens(text)

        text = self._trim_stack_traces(text)
        text = self._dedupe_log_lines(text)
        text = self._summarize_ci_sections(text)
        text = self._normalize_whitespace(text)

        compressed_len = len(text)
        compressed_tokens = self._estimate_tokens(text)

        savings_pct = (
            round((1 - compressed_tokens / original_tokens) * 100, 1)
            if original_tokens > 0
            else 0.0
        )

        stats = {
            "original_chars": original_len,
            "compressed_chars": compressed_len,
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "savings_pct": savings_pct,
        }
        return text, stats

    def compress_file(self, path: Path) -> tuple[str, dict[str, Any]]:
        text = Path(path).read_text(errors="ignore")
        return self.compress(text)

    # ------------------------------------------------------------------
    # Compression passes
    # ------------------------------------------------------------------

    def _trim_stack_traces(self, text: str, keep_frames: int = 5) -> str:
        """Keep first 3 + last N frames of stack traces; replace middle with a count."""

        def _replace_trace(m: re.Match) -> str:
            block = m.group(0)
            lines = block.splitlines()

            frame_lines = [l for l in lines if re.match(r"\s+(?:at |File )", l)]
            if len(frame_lines) <= keep_frames + 3:
                return block  # not worth compressing

            top = frame_lines[:3]
            bottom = frame_lines[-keep_frames:]
            omitted = len(frame_lines) - len(top) - len(bottom)
            mid = [f"    ... {omitted} frames omitted (run with --verbose to see all) ..."]

            non_frame = [l for l in lines if not re.match(r"\s+(?:at |File )", l)]
            return "\n".join(non_frame[:2] + top + mid + bottom)

        # Python tracebacks
        text = re.sub(
            r"Traceback \(most recent call last\):\n(?:.*\n)+?.*Error:.*",
            _replace_trace,
            text,
        )
        # JS/Node tracebacks
        text = re.sub(
            r"(?:Error|TypeError|ReferenceError): .*\n(?:\s+at .*\n)+",
            _replace_trace,
            text,
        )
        return text

    def _dedupe_log_lines(self, text: str, max_repeats: int = 3) -> str:
        """Collapse runs of identical (or near-identical) log lines."""
        lines = text.splitlines(keepends=True)
        out: list[str] = []
        prev = ""
        run = 0

        for line in lines:
            stripped = line.strip()
            if stripped == prev.strip() and stripped:
                run += 1
                if run == max_repeats:
                    out.append(f"    [... repeated {run}+ times — omitted ...]\n")
                elif run > max_repeats:
                    continue  # already noted
                else:
                    out.append(line)
            else:
                prev = line
                run = 1
                out.append(line)

        return "".join(out)

    def _summarize_ci_sections(self, text: str) -> str:
        """Replace passing CI sections with a single summary line."""

        def _replace_passing(m: re.Match) -> str:
            block = m.group(0)
            lines = block.splitlines()
            return f"[CI: {lines[0].strip()} — PASSED ({len(lines)} lines omitted)]"

        # GitHub Actions "Run <step>" blocks that end with a green status
        text = re.sub(
            r"^Run .*\n(?:  .*\n)*?.*\n\n",
            lambda m: _replace_passing(m) if "passed" in m.group(0).lower() else m.group(0),
            text,
            flags=re.MULTILINE,
        )
        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Collapse 3+ blank lines into 2, strip trailing spaces."""
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return text.rstrip() + "\n"

    def _estimate_tokens(self, text: str) -> int:
        try:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return max(1, len(text) // 4)
