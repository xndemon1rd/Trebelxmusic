"""Coding engine for the TrabelxMusic self-healing pipeline.

Flow: error detector -> coding engine -> healer -> validation/rollback.
The coding engine does not execute AI output. It asks the configured AI to produce
an auditable repair package containing a diagnosis, a minimal unified diff and
validation steps. The healer is responsible for applying and validating it.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable

import httpx

ROOT = Path(__file__).resolve().parent
AI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_HEALER_MODEL", "gpt-5.6-luna")
MAX_FILE_CHARS = int(os.getenv("AI_HEALER_MAX_FILE_CHARS", "14000"))
MAX_TRACE_CHARS = int(os.getenv("AI_HEALER_MAX_TRACE_CHARS", "14000"))
MAX_PATCH_CHARS = int(os.getenv("AI_HEALER_MAX_PATCH_CHARS", "50000"))


def _candidate_files(traceback_text: str) -> list[Path]:
    found: list[Path] = []
    for raw in re.findall(r'File ["\']([^"\']+\.py)["\']', traceback_text):
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / p
        try:
            p = p.resolve()
            p.relative_to(ROOT.resolve())
        except ValueError:
            continue
        if p.exists() and p.is_file() and p not in found:
            found.append(p)
    return found[:6]


def _read_context(paths: Iterable[Path]) -> str:
    chunks: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(text) > MAX_FILE_CHARS:
            text = text[:MAX_FILE_CHARS] + "\n# [truncated]\n"
        chunks.append(f"### FILE: {path.relative_to(ROOT)}\n```python\n{text}\n```")
    return "\n\n".join(chunks)


def _response_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    parts: list[str] = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts)


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            obj = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return obj if isinstance(obj, dict) else None


def _normalize_patch(patch: object) -> str | None:
    if not isinstance(patch, str):
        return None
    patch = patch.strip()
    if len(patch) > MAX_PATCH_CHARS:
        return None
    if "*** Begin Patch" in patch:
        patch = patch.split("*** Begin Patch", 1)[1].split("*** End Patch", 1)[0].strip()
    if patch.startswith("```diff"):
        patch = patch[7:].split("```", 1)[0].strip()
    if not (patch.startswith("diff --git ") or re.search(r"^--- .+\n\+\+\+ .+", patch, re.M)):
        return None
    return patch


async def build_repair_package(error: BaseException, traceback_text: str, source: str = "runtime") -> dict:
    """Use the coding model to prepare a repair package for the healer."""
    if not AI_KEY:
        return {"ok": False, "reason": "OPENAI_API_KEY is missing"}

    files = _candidate_files(traceback_text)
    context = _read_context(files)
    if not context:
        return {"ok": False, "reason": "No safe in-repository Python files identified"}

    prompt = f"""You are the coding engine for a production Python Telegram music bot.
Analyze the concrete failure and produce a minimal, safe repair package for a separate healer.
Do not redesign the application. Do not add secrets. Do not execute shell commands.
Only modify files inside the repository. Prefer the smallest root-cause fix.

Return ONLY valid JSON with exactly these keys:
{{
  "diagnosis": "short root-cause explanation",
  "patch": "unified git diff as a string",
  "validation": ["specific checks to run after applying the patch"]
}}
If no safe source-code fix is possible, set patch to an empty string and explain why in diagnosis.

SOURCE: {source}
ERROR TYPE: {type(error).__name__}
TRACEBACK:
{traceback_text[-MAX_TRACE_CHARS:]}

RELEVANT SOURCE:
{context}
"""

    payload = {
        "model": AI_MODEL,
        "input": [
            {"role": "system", "content": "You are a careful software repair/coding engine. Return JSON only."},
            {"role": "user", "content": prompt},
        ],
        "max_output_tokens": 14000,
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {AI_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            obj = _extract_json(_response_text(response.json()))
    except Exception as exc:
        return {"ok": False, "reason": f"Coding engine request failed: {type(exc).__name__}: {exc}"}

    if not obj:
        return {"ok": False, "reason": "Coding engine returned invalid JSON"}
    patch = _normalize_patch(obj.get("patch", ""))
    diagnosis = str(obj.get("diagnosis", "No diagnosis supplied"))[:5000]
    validation = obj.get("validation", [])
    if not isinstance(validation, list):
        validation = [str(validation)]
    return {
        "ok": bool(patch),
        "diagnosis": diagnosis,
        "patch": patch or "",
        "validation": [str(x)[:1000] for x in validation[:12]],
        "files": [str(p.relative_to(ROOT)) for p in files],
        "source": source,
    }
