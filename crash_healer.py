"""Process-level crash detector used by the Railway supervisor."""
from __future__ import annotations

import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    log = ROOT / "runtime.log"
    if not log.exists():
        return 0
    text = log.read_text(encoding="utf-8", errors="replace")[-30000:]
    if "Traceback (most recent call last):" not in text and "SyntaxError:" not in text:
        return 0
    try:
        from ai_healer import repair_error
        error = RuntimeError("Process-level bot crash detected")
        result = asyncio.run(repair_error(error, text, "process_crash"))
        print(f"[AI-HEALER] {result}")
    except Exception as exc:
        print(f"[AI-HEALER] crash analysis failed: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
