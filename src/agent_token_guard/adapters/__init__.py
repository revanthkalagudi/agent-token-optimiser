"""Agent adapters — generate integration files for Claude Code and Codex."""

from .claude import ClaudeAdapter
from .codex import CodexAdapter

__all__ = ["ClaudeAdapter", "CodexAdapter"]
