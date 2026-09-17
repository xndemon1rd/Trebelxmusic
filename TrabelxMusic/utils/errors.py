# Authored By Dev © 2025
"""Centralized error capture and Telegram LOGGER_ID reporting."""
import asyncio
import os
import sys
import threading
import traceback
from datetime import datetime
from functools import wraps

import aiofiles
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden

from TrabelxMusic import app
from config import LOGGER_ID, DEBUG_IGNORE_LOG
from TrabelxMusic.logging import LOGGER
from TrabelxMusic.utils.exceptions import is_ignored_error
from TrabelxMusic.utils.pastebin import TrabelBIN

DEBUG_LOG_FILE = "ignored_errors.log"
_LOCAL_LOGGER = LOGGER("TrabelxMusic.errors")


def _safe_text(value, limit=3500):
    try:
        text = str(value)
    except Exception:
        text = repr(value)
    return text[:limit]


async def send_large_error(text: str, caption: str, filename: str):
    try:
        paste_url = await TrabelBIN(text)
        if paste_url:
            await app.send_message(
                LOGGER_ID,
                f"<blockquote>{caption}\n\n🔗 Paste: {paste_url}</blockquote>",
                disable_web_page_preview=True,
            )
            return
    except Exception as exc:
        _LOCAL_LOGGER.error("Paste fallback failed: %s", exc)

    path = f"{filename}.txt"
    try:
        async with aiofiles.open(path, "w") as f:
            await f.write(text)
        await app.send_document(LOGGER_ID, path, caption="❌ Error Log (Fallback)")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def format_traceback(err, tb, label: str, extras: dict = None) -> str:
    exc_type = type(err).__name__
    parts = [
        f"🚨 <b>{label} Captured</b>",
        f"📍 <b>Error Type:</b> <code>{_safe_text(exc_type, 200)}</code>",
    ]
    if extras:
        for key, value in extras.items():
            parts.append(f"📌 <b>{_safe_text(key, 80)}:</b> <code>{_safe_text(value, 800)}</code>")
    parts.append(f"\n<b>Traceback:</b>\n<pre>{_safe_text(tb, 9000)}</pre>")
    return "\n".join(parts)


async def report_exception(err, tb=None, label="Unhandled Error", extras=None, *, force=False):
    """Report every exception to local logs and LOGGER_ID without crashing the bot."""
    try:
        if tb is None:
            tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))

        _LOCAL_LOGGER.error("%s: %s\n%s", label, err, tb)

        if is_ignored_error(err) and DEBUG_IGNORE_LOG:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                async with aiofiles.open(DEBUG_LOG_FILE, "a") as log:
                    await log.write(
                        f"\n--- Ignored Error | {label} @ {timestamp} ---\n"
                        f"Type: {type(err).__name__}\n"
                        f"{''.join(f'{k}: {v}\n' for k, v in (extras or {}).items())}"
                        f"Traceback:\n{tb.strip()}\n------------------------------------------\n"
                    )
            except Exception as exc:
                _LOCAL_LOGGER.error("Could not write ignored error log: %s", exc)

        caption = format_traceback(err, tb, label, extras)
        try:
            connected = bool(getattr(app, "is_connected", False))
        except Exception:
            connected = False
        if not connected:
            return

        filename = f"error_log_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        if len(caption) > 4096:
            await send_large_error(tb, caption.split("\n\n", 1)[0], filename)
        else:
            await app.send_message(
                LOGGER_ID,
                f"<blockquote>{caption}</blockquote>",
                disable_web_page_preview=True,
            )
    except Exception as report_err:
        _LOCAL_LOGGER.error("LOGGER GC reporting failed: %s", report_err)


async def handle_trace(err, tb, label, filename=None, extras=None):
    # Every captured exception is sent to LOGGER_ID, including errors that are
    # classified as ignorable.  DEBUG_IGNORE_LOG only controls the local file.
    await report_exception(err, tb, label, extras)


# ========== Decorators ==============

def capture_err(func):
    """Handle command errors and report the complete traceback to LOGGER_ID."""
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except ChatWriteForbidden as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            await report_exception(
                err, tb, "Chat Write Forbidden",
                {"User": message.from_user.mention if message.from_user else "N/A",
                 "Chat ID": message.chat.id,
                 "Command": message.text or message.caption},
            )
            try:
                await app.leave_chat(message.chat.id)
            except Exception as leave_err:
                await report_exception(leave_err, label="Leave Chat Error", extras={"Chat ID": message.chat.id})
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            try:
                from TrabelxMusic.utils.error_detector import record
                record(err, tb, "command")
            except Exception as detector_err:
                _LOCAL_LOGGER.error("Error detector failed: %s", detector_err)
            extras = {
                "User": message.from_user.mention if message.from_user else "N/A",
                "Command": message.text or message.caption,
                "Chat ID": message.chat.id,
            }
            await handle_trace(err, tb, "Command Error", None, extras)
            raise
    wrapper._trabel_error_capture = True
    return wrapper


def capture_callback_err(func):
    """Handle callback-query errors and report the complete traceback."""
    @wraps(func)
    async def wrapper(client, callback_query, *args, **kwargs):
        try:
            return await func(client, callback_query, *args, **kwargs)
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            try:
                from TrabelxMusic.utils.error_detector import record
                record(err, tb, "callback")
            except Exception as detector_err:
                _LOCAL_LOGGER.error("Error detector failed: %s", detector_err)
            msg = callback_query.message
            extras = {
                "User": callback_query.from_user.mention if callback_query.from_user else "N/A",
                "Chat ID": msg.chat.id if msg else "N/A",
            }
            await handle_trace(err, tb, "Callback Error", None, extras)
            raise
    wrapper._trabel_error_capture = True
    return wrapper


def capture_internal_err(func):
    """Handle background/internal async errors and report them to LOGGER_ID."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            try:
                from TrabelxMusic.utils.error_detector import record
                record(err, tb, "internal")
            except Exception as detector_err:
                _LOCAL_LOGGER.error("Error detector failed: %s", detector_err)
            await handle_trace(err, tb, "Internal Error", None, {"Function": func.__name__})
            raise
    wrapper._trabel_error_capture = True
    return wrapper


# ========== Global uncaught error hooks ==============
def install_global_error_logging():
    """Install process/thread/asyncio hooks for errors outside decorators."""
    def sys_hook(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _LOCAL_LOGGER.error("UNCAUGHT PROCESS ERROR\n%s", tb)
        try:
            from TrabelxMusic.utils.error_detector import record
            record(exc_value, tb, "process")
        except Exception:
            pass
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(report_exception(exc_value, tb, "Uncaught Process Error"))
        except Exception:
            pass

    def thread_hook(args):
        tb = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        _LOCAL_LOGGER.error("UNCAUGHT THREAD ERROR [%s]\n%s", args.thread.name, tb)
        try:
            from TrabelxMusic.utils.error_detector import record
            record(args.exc_value, tb, "thread")
        except Exception:
            pass
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(report_exception(args.exc_value, tb, "Uncaught Thread Error", {"Thread": args.thread.name}))
        except Exception:
            pass

    def asyncio_hook(loop, context):
        err = context.get("exception") or RuntimeError(context.get("message", "Unknown asyncio error"))
        tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
        extras = {"Task": str(context.get("future") or context.get("task") or "N/A")[:500]}
        _LOCAL_LOGGER.error("UNHANDLED ASYNCIO ERROR\n%s", tb)
        try:
            loop.create_task(report_exception(err, tb, "Unhandled Asyncio Error", extras))
        except Exception:
            pass

    sys.excepthook = sys_hook
    try:
        threading.excepthook = thread_hook
    except Exception:
        pass
    try:
        asyncio.get_event_loop().set_exception_handler(asyncio_hook)
    except Exception:
        pass
