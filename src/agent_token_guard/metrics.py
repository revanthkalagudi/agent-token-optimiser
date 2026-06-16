"""Metrics engine — track token savings across sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_GUARD_DIR = ".agent-token-guard"
_METRICS_FILE = f"{_GUARD_DIR}/metrics/usage.jsonl"

# Rough cost per 1M tokens for Claude Sonnet 4.5 (input/output blended estimate)
_COST_PER_1M_TOKENS = 4.50


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class MetricsEngine:
    """Append-only usage log with summary reporting."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()
        self.metrics_file = self.root / _METRICS_FILE
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        event: str,
        tokens_before: int = 0,
        tokens_after: int = 0,
        files_avoided: int = 0,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Append one usage event to usage.jsonl."""
        entry: dict[str, Any] = {
            "ts": _now_iso(),
            "event": event,
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "tokens_saved": max(0, tokens_before - tokens_after),
            "files_avoided": files_avoided,
        }
        if extra:
            entry.update(extra)

        with self.metrics_file.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")

    def report(self) -> dict[str, Any]:
        """Return an aggregated summary across all recorded events."""
        events = self._load_events()
        if not events:
            return {
                "sessions": 0,
                "total_tokens_saved": 0,
                "total_files_avoided": 0,
                "estimated_cost_saved_usd": 0.0,
                "events": [],
            }

        total_saved = sum(e.get("tokens_saved", 0) for e in events)
        total_files = sum(e.get("files_avoided", 0) for e in events)
        sessions = sum(1 for e in events if e.get("event") in ("save", "resume"))
        cost_saved = round(total_saved / 1_000_000 * _COST_PER_1M_TOKENS, 4)

        return {
            "sessions": sessions,
            "total_tokens_saved": total_saved,
            "total_files_avoided": total_files,
            "estimated_cost_saved_usd": cost_saved,
            "events": events,
        }

    def summary_text(self) -> str:
        """Human-readable one-line summary for CLI output."""
        r = self.report()
        if r["sessions"] == 0:
            return "No sessions recorded yet. Run `atg save` after your first session."
        return (
            f"{r['sessions']} sessions | "
            f"{r['total_tokens_saved']:,} tokens saved | "
            f"{r['total_files_avoided']} files avoided | "
            f"~${r['estimated_cost_saved_usd']:.4f} saved"
        )

    def clear(self) -> None:
        """Wipe the usage log (start fresh)."""
        if self.metrics_file.exists():
            self.metrics_file.write_text("")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_events(self) -> list[dict[str, Any]]:
        if not self.metrics_file.exists():
            return []
        events = []
        for line in self.metrics_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events
