"""
TrabelxMusic self-healing bootstrap.

This module deliberately uses conservative, deterministic repairs only.  It does
not rewrite arbitrary Python code or execute instructions obtained from remote
content.  It repairs known deployment/runtime drift, validates the repository,
and records what it did.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "repair_report.json"
LOCK = ROOT / ".repair.lock"


def _log(report: dict, message: str) -> None:
    report.setdefault("actions", []).append(message)


def _remove_python_cache(report: dict) -> None:
    removed = 0
    for path in ROOT.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    for path in ROOT.rglob("*.pyc"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    for path in ROOT.rglob("*.pyo"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    if removed:
        _log(report, f"Removed {removed} Python cache artifacts")


def _ensure_directories(report: dict) -> None:
    for name in ("downloads", "cache", "couples", "TrabelxMusicBackup"):
        path = ROOT / name
        path.mkdir(parents=True, exist_ok=True)


def _repair_dockerfile(report: dict) -> None:
    path = ROOT / "Dockerfile"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    original = text

    # Deno's official installer needs unzip or 7z in the base image.
    if "apt-get install" in text and "unzip" not in text:
        text = text.replace(
            "git ffmpeg curl ca-certificates",
            "git ffmpeg curl ca-certificates unzip",
        )

    if text != original:
        path.write_text(text, encoding="utf-8")
        _log(report, "Repaired Dockerfile: added unzip for Deno installation")


def _repair_requirements(report: dict) -> None:
    path = ROOT / "requirements.txt"
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    # Keep the recommended yt-dlp default extra; avoid duplicate standalone EJS
    # packages that can drift away from the installed yt-dlp version.
    cleaned = []
    seen = set()
    for line in lines:
        stripped = line.strip()
        key = stripped.lower()
        if key.startswith("yt-dlp-ejs"):
            continue
        if key == "asyncio":
            # asyncio is part of Python's standard library.
            continue
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        cleaned.append(line)
    if not any(line.strip().lower().startswith("yt-dlp[default]") for line in cleaned):
        cleaned.append("yt-dlp[default]>=2026.08.19")
    new = "\n".join(cleaned).rstrip() + "\n"
    if new != path.read_text(encoding="utf-8", errors="replace"):
        path.write_text(new, encoding="utf-8")
        _log(report, "Normalized requirements.txt")


def _syntax_check(report: dict) -> bool:
    errors: List[str] = []
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"{path.relative_to(ROOT)}:{exc.lineno}:{exc.offset}: {exc.msg}")
    report["python_syntax_errors"] = errors
    return not errors


def _ensure_deno(report: dict) -> None:
    if shutil.which("deno"):
        return
    installer = shutil.which("curl")
    unzip = shutil.which("unzip") or shutil.which("7z")
    if not installer or not unzip:
        _log(report, "Deno missing and automatic installation prerequisites are unavailable")
        return
    script = ROOT / ".deno_install.sh"
    try:
        # Fetch the fixed official installer without invoking a shell pipeline.
        subprocess.run(
            [installer, "-fsSL", "https://deno.land/install.sh", "-o", str(script)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        subprocess.run(
            ["sh", str(script)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        source = Path("/root/.deno/bin/deno")
        target = Path("/usr/local/bin/deno")
        if source.exists() and os.access("/usr/local/bin", os.W_OK):
            target.symlink_to(source, target_is_directory=False) if not target.exists() else None
        if shutil.which("deno"):
            _log(report, "Automatically restored missing Deno runtime")
        else:
            _log(report, "Deno installer completed but executable was not found on PATH")
    except Exception as exc:
        _log(report, f"Automatic Deno repair failed: {type(exc).__name__}: {exc}")
    finally:
        try:
            script.unlink(missing_ok=True)
        except OSError:
            pass


def _ai_repair_startup(report: dict) -> None:
    """If local validation finds syntax errors, optionally ask the AI healer to fix them."""
    if report.get("python_syntax_ok"):
        return
    try:
        import asyncio
        from ai_healer import repair_error
        errors = "\n".join(report.get("python_syntax_errors", []))
        err = SyntaxError(errors)
        result = asyncio.run(repair_error(err, errors, "startup"))
        report["ai_repair"] = result
        if result.get("repaired"):
            report["python_syntax_ok"] = _syntax_check(report)
    except Exception as exc:
        report["ai_repair"] = {"repaired": False, "reason": f"{type(exc).__name__}: {exc}"}

def run_startup_repair() -> dict:
    """Run safe local repairs once per process and return a diagnostic report."""
    report = {
        "timestamp": int(time.time()),
        "root": str(ROOT),
        "actions": [],
    }
    # Avoid two repairers running at once if the process is accidentally started twice.
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        owner = True
    except FileExistsError:
        owner = False

    try:
        if not owner:
            report["actions"].append("Repair already running; validation only")
            report["python_syntax_ok"] = _syntax_check(report)
            return report

        _remove_python_cache(report)
        _ensure_directories(report)
        _repair_dockerfile(report)
        _repair_requirements(report)
        _ensure_deno(report)
        report["python_syntax_ok"] = _syntax_check(report)
        _ai_repair_startup(report)
        report["required_files_ok"] = all(
            (ROOT / name).exists()
            for name in ("Dockerfile", "requirements.txt", "config.py", "TrabelxMusic", "strings")
        )
        try:
            REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except OSError:
            pass
        return report
    finally:
        if owner:
            try:
                LOCK.unlink()
            except OSError:
                pass
