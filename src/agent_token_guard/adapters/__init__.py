"""Agent adapters — generate integration files for supported assistant platforms."""

from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .platforms import AgentsAdapter, CopilotAdapter, CursorAdapter

__all__ = [
    "ClaudeAdapter",
    "CodexAdapter",
    "CopilotAdapter",
    "CursorAdapter",
    "AgentsAdapter",
]
