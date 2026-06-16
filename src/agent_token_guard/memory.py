"""Session memory manager — save/resume agent context across sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

_GUARD_DIR = ".agent-token-guard"
_MEMORY_DIR = f"{_GUARD_DIR}/memory"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _estimate_tokens(text: str) -> int:
    """Rough 1 token ≈ 4 chars estimate (no tiktoken dep at runtime for speed)."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


class MemoryManager:
    """Persist and retrieve session context to avoid re-sending the same info."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()
        self.memory_dir = self.root / _MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        summary: str,
        decisions: list[str] | None = None,
        todos: list[str] | None = None,
        touched_files: list[str] | None = None,
        next_steps: str | None = None,
    ) -> dict[str, int]:
        """Persist a session snapshot. Returns token counts before/after."""
        payload = {
            "saved_at": _now_iso(),
            "summary": summary,
            "decisions": decisions or [],
            "todos": todos or [],
            "touched_files": touched_files or [],
            "next_steps": next_steps or "",
        }

        full_text = json.dumps(payload, indent=2)
        tokens_full = _estimate_tokens(full_text)

        self._write_session(payload)
        self._write_decisions(payload["decisions"])
        self._write_todos(payload["todos"])

        compact = self._build_compact_context(payload)
        tokens_compact = _estimate_tokens(compact)

        return {
            "tokens_full": tokens_full,
            "tokens_compact": tokens_compact,
            "saved_at": payload["saved_at"],
        }

    def resume(self) -> str:
        """Return a compact context block ready to paste at session start."""
        session_file = self.memory_dir / "session.md"
        if not session_file.exists():
            return "No saved session found. Run `atg save` after your first session."

        raw = session_file.read_text()
        payload = self._parse_frontmatter(raw)
        return self._build_compact_context(payload)

    def load_raw(self) -> dict[str, Any]:
        """Load the full saved session as a dict."""
        session_file = self.memory_dir / "session.md"
        if not session_file.exists():
            return {}
        return self._parse_frontmatter(session_file.read_text())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _write_session(self, payload: dict[str, Any]) -> None:
        content = self._frontmatter(payload) + self._session_body(payload)
        (self.memory_dir / "session.md").write_text(content)

    def _write_decisions(self, decisions: list[str]) -> None:
        lines = "\n".join(f"- {d}" for d in decisions) if decisions else "_None yet._"
        (self.memory_dir / "decisions.md").write_text(
            f"# Decisions Log\n\n_Last updated: {_now_iso()}_\n\n{lines}\n"
        )

    def _write_todos(self, todos: list[str]) -> None:
        lines = "\n".join(f"- [ ] {t}" for t in todos) if todos else "_No open tasks._"
        (self.memory_dir / "todo.md").write_text(
            f"# Open TODOs\n\n_Last updated: {_now_iso()}_\n\n{lines}\n"
        )

    def _frontmatter(self, payload: dict[str, Any]) -> str:
        meta = {
            "saved_at": payload.get("saved_at", ""),
            "touched_files": payload.get("touched_files", []),
        }
        return f"---\n{yaml.dump(meta, default_flow_style=False)}---\n\n"

    def _session_body(self, payload: dict[str, Any]) -> str:
        parts: list[str] = [f"# Session Summary\n\n{payload.get('summary', '')}\n"]

        decisions = payload.get("decisions", [])
        if decisions:
            parts.append("\n## Key Decisions\n")
            parts.extend(f"- {d}\n" for d in decisions)

        todos = payload.get("todos", [])
        if todos:
            parts.append("\n## Open TODOs\n")
            parts.extend(f"- [ ] {t}\n" for t in todos)

        touched = payload.get("touched_files", [])
        if touched:
            parts.append("\n## Touched Files\n")
            parts.extend(f"- `{f}`\n" for f in touched)

        next_steps = payload.get("next_steps", "")
        if next_steps:
            parts.append(f"\n## Next Steps\n\n{next_steps}\n")

        return "".join(parts)

    def _build_compact_context(self, payload: dict[str, Any]) -> str:
        """Minimal context for session start — avoids verbose re-explanation."""
        lines: list[str] = [
            "<!-- agent-token-guard: session context -->",
            f"**Last saved:** {payload.get('saved_at', 'unknown')}",
            "",
            f"**Summary:** {payload.get('summary', '').strip()}",
        ]

        decisions = payload.get("decisions", [])
        if decisions:
            lines.append("\n**Decisions:** " + " | ".join(decisions))

        todos = payload.get("todos", [])
        if todos:
            lines.append("\n**Open TODOs:**")
            lines.extend(f"  - {t}" for t in todos)

        touched = payload.get("touched_files", [])
        if touched:
            lines.append("\n**Touched files:** " + ", ".join(f"`{f}`" for f in touched))

        next_steps = payload.get("next_steps", "").strip()
        if next_steps:
            lines.append(f"\n**Next:** {next_steps}")

        lines.append("<!-- end agent-token-guard -->")
        return "\n".join(lines)

    def _parse_frontmatter(self, text: str) -> dict[str, Any]:
        """Parse YAML frontmatter + markdown body into a dict."""
        if not text.startswith("---"):
            return {"summary": text}

        _, rest = text.split("---", 1)
        fm_raw, body = rest.split("---", 1)
        meta: dict[str, Any] = yaml.safe_load(fm_raw) or {}

        # Extract sections from body
        meta["summary"] = self._extract_section(body, "Session Summary")
        meta.setdefault("decisions", self._extract_list_section(body, "Key Decisions"))
        meta.setdefault("todos", self._extract_list_section(body, "Open TODOs"))
        meta.setdefault("next_steps", self._extract_section(body, "Next Steps"))
        return meta

    def _extract_section(self, body: str, heading: str) -> str:
        import re

        pattern = rf"##? {re.escape(heading)}\n+(.*?)(?=\n##? |\Z)"
        m = re.search(pattern, body, re.DOTALL)
        return m.group(1).strip() if m else ""

    def _extract_list_section(self, body: str, heading: str) -> list[str]:
        import re

        section = self._extract_section(body, heading)
        items = re.findall(r"^[-*]\s+(?:\[.\]\s+)?(.+)$", section, re.MULTILINE)
        return items
