"""Environment diagnostics for AgentTokenGuard."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    fix: str = ""


class Doctor:
    """Run dependency and environment checks for a repository."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()

    def run(self) -> dict[str, Any]:
        checks = [
            self._python_version_check(),
            self._python_modules_check(),
            self._git_binary_check(),
            self._git_repo_check(),
            self._guard_dir_writable_check(),
        ]
        passed = sum(1 for c in checks if c.ok)
        failed = len(checks) - passed
        return {
            "passed": passed,
            "failed": failed,
            "checks": [asdict(c) for c in checks],
            "ok": failed == 0,
        }

    def _python_version_check(self) -> CheckResult:
        required = (3, 9)
        current = sys.version_info[:3]
        ok = current >= required
        detail = f"Python {current[0]}.{current[1]}.{current[2]}"
        fix = "Use Python 3.9+ to run AgentTokenGuard." if not ok else ""
        return CheckResult("python-version", ok, detail, fix)

    def _python_modules_check(self) -> CheckResult:
        required = ["typer", "rich", "yaml", "git"]
        missing = [name for name in required if importlib.util.find_spec(name) is None]
        tokenizer_ok = importlib.util.find_spec("tiktoken") is not None

        if missing:
            return CheckResult(
                "python-modules",
                False,
                f"missing: {', '.join(missing)}",
                "Install dependencies: pip install -e .",
            )

        detail = "core modules present"
        if not tokenizer_ok:
            detail += "; tiktoken missing (fallback estimator active)"
        return CheckResult("python-modules", True, detail)

    def _git_binary_check(self) -> CheckResult:
        git = shutil.which("git")
        if not git:
            return CheckResult(
                "git-binary",
                False,
                "git not found in PATH",
                "Install Git and ensure it is available in PATH.",
            )
        return CheckResult("git-binary", True, f"git found: {git}")

    def _git_repo_check(self) -> CheckResult:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True,
                cwd=self.root,
            )
            if result.returncode == 0 and result.stdout.strip().lower() == "true":
                return CheckResult("git-repo", True, "inside git work tree")
            return CheckResult(
                "git-repo",
                False,
                "not inside a git repository",
                "Run atg inside a git repo to enable changed-files auto-detection.",
            )
        except Exception as exc:
            return CheckResult("git-repo", False, f"git check failed: {exc}")

    def _guard_dir_writable_check(self) -> CheckResult:
        guard = self.root / ".agent-token-guard"
        try:
            guard.mkdir(parents=True, exist_ok=True)
            probe = guard / ".write-test"
            probe.write_text("ok")
            probe.unlink(missing_ok=True)
            return CheckResult("guard-dir", True, f"writable: {guard}")
        except Exception as exc:
            return CheckResult(
                "guard-dir",
                False,
                f"not writable: {guard} ({exc})",
                "Fix filesystem permissions for the repository.",
            )