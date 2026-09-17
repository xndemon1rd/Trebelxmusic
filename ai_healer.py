"""AI-assisted error detector and conservative self-repair engine.

The AI is optional. It receives an exception plus a small set of relevant source
files and may return a unified diff. The diff is checked with `git apply --check`
when Git is available, then syntax-checked. Any failed validation is rolled back.
No remote text is executed as shell commands.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
AI_HEALER_MODE = os.getenv("AI_HEALER_ENABLED", "auto").strip().lower()
AI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
AI_ENABLED = AI_HEALER_MODE in {"1", "true", "yes", "on", "auto"} and bool(AI_KEY)
if AI_HEALER_MODE in {"0", "false", "no", "off"}:
    AI_ENABLED = False
AI_MODEL = os.getenv("AI_HEALER_MODEL", "gpt-5.6-luna")
MAX_FILE_CHARS = int(os.getenv("AI_HEALER_MAX_FILE_CHARS", "14000"))
MAX_PATCH_CHARS = int(os.getenv("AI_HEALER_MAX_PATCH_CHARS", "50000"))
_LOCK = asyncio.Lock()


def enabled() -> bool:
    return AI_ENABLED and bool(AI_KEY)


async def _get_coding_package(error: BaseException, traceback_text: str, source: str) -> dict:
    from coding_engine import build_repair_package
    return await build_repair_package(error, traceback_text, source)


def _git_available() -> bool:
    if shutil.which("git") is None:
        return False
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        )
        return probe.returncode == 0 and probe.stdout.strip() == "true"
    except Exception:
        return False


def _run_patch_command(patch: str, check_only: bool) -> bool:
    if _git_available():
        args = ["git", "apply", "--whitespace=nowarn"]
        if check_only:
            args.append("--check")
        args.append("-")
    elif shutil.which("patch"):
        args = ["patch", "--batch", "--forward", "-p1"]
        if check_only:
            args.append("--dry-run")
    else:
        return False
    p = subprocess.run(args, cwd=ROOT, input=patch, text=True, capture_output=True, timeout=45)
    return p.returncode == 0


def _check_patch(patch: str) -> bool:
    return _run_patch_command(patch, True)


def _apply_patch(patch: str) -> bool:
    return _run_patch_command(patch, False)


def _syntax_check() -> tuple[bool, str]:
    p = subprocess.run(
        ["python3", "-m", "compileall", "-q", str(ROOT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=90,
    )
    return p.returncode == 0, (p.stdout + p.stderr)[-6000:]


def _backup(paths: Iterable[Path]) -> dict[Path, bytes | None]:
    backup = {}
    for p in paths:
        try:
            backup[p] = p.read_bytes()
        except FileNotFoundError:
            backup[p] = None
    return backup


def _restore(backup: dict[Path, bytes | None]) -> None:
    for p, data in backup.items():
        if data is None:
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)


async def repair_error(error: BaseException, traceback_text: str, source: str = "runtime") -> dict:
    """Ask the coding engine for a patch, then validate/apply it conservatively."""
    result = {"enabled": enabled(), "source": source, "repaired": False, "reason": ""}
    if not enabled():
        result["reason"] = "AI_HEALER_ENABLED is false or OPENAI_API_KEY is missing"
        return result

    async with _LOCK:
        package = await _get_coding_package(error, traceback_text, source)
        result["diagnosis"] = package.get("diagnosis", "")
        result["validation_plan"] = package.get("validation", [])
        if not package.get("ok"):
            result["reason"] = package.get("reason", "Coding engine produced no safe patch")
            return result

        patch = package["patch"]
        if not _check_patch(patch):
            result["reason"] = "Patch failed validation before application"
            return result

        affected = []
        for line in patch.splitlines():
            if line.startswith("+++ b/"):
                rel = line[6:].strip()
                if not rel.endswith(".py"):
                    result["reason"] = "AI repair patches are restricted to Python source files"
                    return result
                p = (ROOT / rel).resolve()
                try:
                    p.relative_to(ROOT.resolve())
                except ValueError:
                    result["reason"] = "Patch referenced a file outside repository root"
                    return result
                if p not in affected:
                    affected.append(p)
        if not affected or len(affected) > 4:
            result["reason"] = "Repair must target between 1 and 4 Python files"
            return result
        backup = _backup(affected)
        if not _apply_patch(patch):
            result["reason"] = "Patch application failed"
            return result

        ok, details = _syntax_check()
        if not ok:
            _restore(backup)
            result["reason"] = "Repair introduced a Python syntax error; rolled back"
            result["validation"] = details
            return result

        result["repaired"] = True
        result["reason"] = "Coding-engine patch validated and applied successfully"
        result["files"] = [str(p.relative_to(ROOT)) for p in affected]
        result["timestamp"] = int(time.time())
        try:
            (ROOT / "ai_repair_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            # The running process already imported old Python modules. Ask the
            # Railway supervisor to restart so the validated repair is loaded.
            (ROOT / ".self_heal_restart").write_text("validated repair\n", encoding="utf-8")
        except OSError:
            pass
        return result
