"""Central error detector: records failures and forwards them to the coding engine/healer."""
from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
import traceback
import hashlib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ERROR_LOG = ROOT / "self_healing_errors.jsonl"
_INSTALLED = False
_ATTEMPTS = defaultdict(int)
_MAX_ATTEMPTS = 3



def _deterministic_repair(error: BaseException, traceback_text: str) -> str | None:
    """Return a deterministic repair action for known, non-AI failures.

    These are runtime safety nets, not arbitrary source rewriting. The current
    process is protected immediately; the AI healer is only used for unknown
    failures after this layer.
    """
    text = f"{type(error).__name__}: {error}\n{traceback_text}".lower()
    if "unexpected keyword argument 'quote'" in text or 'unexpected keyword argument "quote"' in text:
        try:
            from TrabelxMusic.core.bot import _install_reply_compatibility
            _install_reply_compatibility()
            return "Reinstalled Kurigram reply compatibility shim for legacy quote= usage"
        except Exception:
            return None
    if "cookie_url" in text and "not set" in text:
        # Missing COOKIE_URL is intentionally non-fatal. The cookie loader now
        # supports YTDLP_COOKIES_B64 and can continue without cookies.
        return "Marked missing COOKIE_URL as non-fatal; cookie loading continues without cookies"
    return None

def _dispatch(error: BaseException, traceback_text: str, source: str) -> None:
    # Prevent one repeating exception from causing an endless AI-repair loop.
    fingerprint = hashlib.sha256(
        f"{type(error).__name__}|{str(error)}|{traceback_text[-4000:]}".encode("utf-8", "replace")
    ).hexdigest()[:20]
    if _ATTEMPTS[fingerprint] >= _MAX_ATTEMPTS:
        return
    _ATTEMPTS[fingerprint] += 1
    try:
        deterministic = _deterministic_repair(error, traceback_text)
        if deterministic:
            return
    except Exception:
        pass
    try:
        from ai_healer import repair_error
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            def runner():
                try:
                    asyncio.run(repair_error(error, traceback_text, source))
                except Exception:
                    pass
            threading.Thread(target=runner, name="trebel-self-healer", daemon=True).start()
        else:
            loop.create_task(repair_error(error, traceback_text, source))
    except Exception:
        pass


def record(error: BaseException, traceback_text: str, source: str = "runtime") -> None:
    event = {
        "timestamp": int(time.time()),
        "source": source,
        "type": type(error).__name__,
        "message": str(error)[:2000],
        "traceback": traceback_text[-16000:],
    }
    try:
        with ERROR_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        pass
    _dispatch(error, traceback_text, source)


def install() -> None:
    """Install process/asyncio-level detectors once."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()

    def loop_handler(current_loop, context):
        exc = context.get("exception") or RuntimeError(context.get("message", "Unhandled asyncio exception"))
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        record(exc, tb, "asyncio")
        if previous_handler:
            previous_handler(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(loop_handler)

    def excepthook(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        record(exc_value, tb, "process")
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = excepthook
