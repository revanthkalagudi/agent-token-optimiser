"""Repo context indexer — builds file-map, dependency-map, and repo summary."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_GUARD_DIR = ".agent-token-guard"
_INDEX_DIR = f"{_GUARD_DIR}/index"

_IGNORE_DIRS = {
    "node_modules", ".git", ".hg", ".svn", "dist", "build", "target",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "vendor", ".venv", "venv", "env", ".env", "coverage", ".coverage",
    "htmlcov", ".tox", "eggs", ".eggs", "*.egg-info",
}

_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".kt",
    ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".scala",
    ".sh", ".bash", ".zsh", ".fish",
}

_CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".env.example", ".editorconfig",
}

_DOC_EXTENSIONS = {".md", ".rst", ".txt"}

_LARGE_FILE_BYTES = 100_000  # files > 100 KB get flagged


def _should_ignore(path: Path) -> bool:
    for part in path.parts:
        if part in _IGNORE_DIRS or part.endswith(".egg-info"):
            return True
    return False


class RepoIndexer:
    """Walk a repo and build a lightweight context index."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()
        self.index_dir = self.root / _INDEX_DIR
        self.index_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index(self) -> dict[str, Any]:
        """Run a full index pass. Returns a summary dict."""
        file_map = self._build_file_map()
        dep_map = self._build_dependency_map(file_map)
        summary = self._build_repo_summary(file_map)

        (self.index_dir / "file-map.json").write_text(
            json.dumps(file_map, indent=2)
        )
        (self.index_dir / "dependency-map.json").write_text(
            json.dumps(dep_map, indent=2)
        )
        self._write_repo_summary(summary)

        return {
            "total_files": summary["total_files"],
            "code_files": summary["code_files"],
            "large_files": len(summary["large_files"]),
            "entry_points": summary["entry_points"],
        }

    def get_changed_files(self) -> list[str]:
        """Return files modified since the last git commit (if in a git repo)."""
        try:
            import subprocess

            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.root,
            )
            if result.returncode == 0:
                return [Path(f).as_posix() for f in result.stdout.splitlines() if f.strip()]
        except Exception:
            pass
        return []

    def get_repo_summary_text(self) -> str:
        """Return the repo-summary.md contents (or a placeholder)."""
        summary_file = self.root / _GUARD_DIR / "memory" / "repo-summary.md"
        if summary_file.exists():
            return summary_file.read_text()
        return "_No repo summary found. Run `atg index` to generate one._"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_file_map(self) -> dict[str, Any]:
        file_map: dict[str, Any] = {}

        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root)
            if _should_ignore(rel):
                continue

            ext = path.suffix.lower()
            size = path.stat().st_size

            category = "other"
            if ext in _CODE_EXTENSIONS:
                category = "code"
            elif ext in _CONFIG_EXTENSIONS:
                category = "config"
            elif ext in _DOC_EXTENSIONS:
                category = "doc"

            file_map[rel.as_posix()] = {
                "category": category,
                "ext": ext,
                "size_bytes": size,
                "large": size > _LARGE_FILE_BYTES,
            }

        return file_map

    def _build_dependency_map(self, file_map: dict[str, Any]) -> dict[str, list[str]]:
        dep_map: dict[str, list[str]] = {}

        for rel_str, meta in file_map.items():
            if meta["category"] != "code":
                continue
            path = self.root / rel_str
            imports = self._extract_imports(path, meta["ext"])
            if imports:
                dep_map[rel_str] = imports

        return dep_map

    def _extract_imports(self, path: Path, ext: str) -> list[str]:
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            return []

        imports: list[str] = []
        if ext == ".py":
            for m in re.finditer(r"^(?:import|from)\s+([\w.]+)", text, re.MULTILINE):
                imports.append(m.group(1))
        elif ext in {".js", ".ts", ".jsx", ".tsx"}:
            for m in re.finditer(
                r'(?:import|require)\s*\(?["\']([^"\']+)["\']', text
            ):
                imports.append(m.group(1))
        elif ext == ".go":
            for m in re.finditer(r'"([^"]+)"', text):
                val = m.group(1)
                if "/" in val:
                    imports.append(val)
        elif ext == ".rs":
            for m in re.finditer(r"^use\s+([\w:]+)", text, re.MULTILINE):
                imports.append(m.group(1))

        return sorted(set(imports))

    def _build_repo_summary(self, file_map: dict[str, Any]) -> dict[str, Any]:
        total = len(file_map)
        code_files = [k for k, v in file_map.items() if v["category"] == "code"]
        config_files = [k for k, v in file_map.items() if v["category"] == "config"]
        doc_files = [k for k, v in file_map.items() if v["category"] == "doc"]
        large_files = [k for k, v in file_map.items() if v["large"]]

        entry_points = self._detect_entry_points(file_map)
        lang = self._detect_primary_language(code_files)

        return {
            "total_files": total,
            "code_files": len(code_files),
            "config_files": len(config_files),
            "doc_files": len(doc_files),
            "large_files": large_files,
            "entry_points": entry_points,
            "primary_language": lang,
            "top_code_files": code_files[:30],
        }

    def _detect_entry_points(self, file_map: dict[str, Any]) -> list[str]:
        candidates = [
            "main.py", "app.py", "server.py", "index.py", "cli.py",
            "main.go", "main.rs", "index.js", "index.ts", "app.js",
            "app.ts", "server.js", "server.ts",
        ]
        found = []
        for rel_str in file_map:
            if Path(rel_str).name in candidates:
                found.append(rel_str)
        return found

    def _detect_primary_language(self, code_files: list[str]) -> str:
        from collections import Counter

        exts = Counter(Path(f).suffix.lower() for f in code_files)
        if not exts:
            return "unknown"
        ext_to_lang = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
            ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".swift": "Swift",
            ".c": "C", ".cpp": "C++", ".scala": "Scala",
        }
        top_ext, _ = exts.most_common(1)[0]
        return ext_to_lang.get(top_ext, top_ext.lstrip(".").upper())

    def _write_repo_summary(self, summary: dict[str, Any]) -> None:
        memory_dir = self.root / _GUARD_DIR / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Repo Summary",
            "",
            f"**Primary language:** {summary['primary_language']}",
            f"**Total files:** {summary['total_files']} "
            f"({summary['code_files']} code, {summary['config_files']} config, "
            f"{summary['doc_files']} docs)",
            "",
        ]

        if summary["entry_points"]:
            lines += ["## Entry Points", ""]
            lines += [f"- `{e}`" for e in summary["entry_points"]]
            lines.append("")

        if summary["top_code_files"]:
            lines += ["## Key Source Files", ""]
            lines += [f"- `{f}`" for f in summary["top_code_files"]]
            lines.append("")

        if summary["large_files"]:
            lines += [
                "## Large Files (>100 KB — read only if necessary)",
                "",
            ]
            lines += [f"- `{f}`" for f in summary["large_files"]]
            lines.append("")

        (memory_dir / "repo-summary.md").write_text("\n".join(lines))
