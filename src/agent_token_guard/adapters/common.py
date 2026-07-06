"""Shared helpers for adapter-managed file generation and cleanup."""

from __future__ import annotations

from pathlib import Path

_BEGIN = "<!-- AGENT_TOKEN_GUARD:BEGIN -->"
_END = "<!-- AGENT_TOKEN_GUARD:END -->"


def managed_block(content: str) -> str:
    """Wrap content in stable markers so uninstall can remove it safely."""
    body = content.strip() + "\n"
    return f"{_BEGIN}\n{body}{_END}\n"


def upsert_managed_section(path: Path, section: str) -> str:
    """Insert or replace the managed section in a markdown-like file."""
    section = managed_block(section)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(section)
        return "created"

    existing = path.read_text()
    if _BEGIN in existing and _END in existing:
        before, rest = existing.split(_BEGIN, 1)
        _, after = rest.split(_END, 1)
        merged = before.rstrip() + "\n\n" + section + after
        path.write_text(merged.strip() + "\n")
        return "updated"

    if "agent-token-guard" in existing.lower():
        return "skipped"

    path.write_text(existing.rstrip() + "\n\n" + section)
    return "appended"


def remove_managed_section(path: Path) -> bool:
    """Remove only the managed section from a file. Deletes file if now empty."""
    if not path.exists():
        return False

    text = path.read_text()
    if _BEGIN not in text or _END not in text:
        return False

    before, rest = text.split(_BEGIN, 1)
    _, after = rest.split(_END, 1)
    merged = (before + after).strip()

    if merged:
        path.write_text(merged + "\n")
    else:
        path.unlink(missing_ok=True)
    return True


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n")


def remove_file(path: Path) -> bool:
    if not path.exists():
        return False
    path.unlink(missing_ok=True)
    return True