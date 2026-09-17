# Authored By Dev © 2025
"""Optional YouTube cookie bootstrap with URL/Base64 support.

Cookies are never required for normal startup. If configured, they are validated
and written atomically so a bad/partial download cannot replace a good cookie file.
"""
import asyncio
import base64
import binascii
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import requests

from config import COOKIE_URL, YTDLP_COOKIES_B64

COOKIE_PATH = Path("TrabelxMusic/assets/cookies.txt")


def _extract_paste_id(url: str) -> str:
    path = urlsplit(url).path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    return parts[-1] if parts else ""


def resolve_raw_cookie_url(url: str) -> str:
    url = (url or "").strip()
    low = url.lower()

    if "pastebin.com/" in low and "/raw/" not in low:
        paste_id = _extract_paste_id(url)
        return f"https://pastebin.com/raw/{paste_id}" if paste_id else url

    if "batbin.me/" in low:
        if "/api/v2/paste/" in low:
            return url
        paste_id = _extract_paste_id(url)
        return f"https://batbin.me/api/v2/paste/{paste_id}" if paste_id else url

    return url


def _validate_cookies(text: str) -> str:
    """Validate a Netscape cookies.txt payload without logging its contents.

    yt-dlp accepts Mozilla/Netscape cookie files.  We validate the header and
    individual rows so truncated HTML/error pages, malformed exports and
    accidental JSON/CSV uploads never replace a working cookie file.
    Expired rows are allowed because a cookie jar can legitimately contain a
    mixture of expired and live cookies.
    """
    cookies = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = cookies.splitlines()
    if not lines or lines[0].strip() not in {
        "# Netscape HTTP Cookie File",
        "# HTTP Cookie File",
        "# Netscape Cookie File",
    }:
        raise ValueError("Invalid cookies format: expected Mozilla/Netscape cookies.txt format")

    valid_rows = 0
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 7:
            raise ValueError("Invalid cookies format: malformed Netscape cookie row")
        domain, _flag, path, secure, expires, _name, _value = fields
        if not domain or not path or secure not in {"TRUE", "FALSE"}:
            raise ValueError("Invalid cookies format: malformed Netscape cookie fields")
        try:
            expiry = int(expires)
        except ValueError as exc:
            raise ValueError("Invalid cookies format: cookie expiry is not numeric") from exc
        if expiry < 0:
            raise ValueError("Invalid cookies format: negative cookie expiry")
        valid_rows += 1

    if valid_rows == 0:
        raise ValueError("Cookie file contains no valid cookie rows")
    return "\n".join(lines) + "\n"

def _decode_b64(value: str) -> str:
    compact = "".join((value or "").split())
    if not compact:
        return ""
    try:
        raw = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("YTDLP_COOKIES_B64 is not valid Base64") from exc
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("YTDLP_COOKIES_B64 is not UTF-8 cookies.txt data") from exc


def _atomic_store(text: str) -> None:
    COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".cookies.", dir=str(COOKIE_PATH.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.chmod(tmp_name, 0o600)
        except OSError:
            pass
        os.replace(tmp_name, COOKIE_PATH)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def _read_existing_cookie_file() -> str:
    try:
        if not COOKIE_PATH.is_file() or COOKIE_PATH.stat().st_size < 100:
            return ""
        return COOKIE_PATH.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError):
        return ""


def _existing_cookie_file_is_usable() -> bool:
    text = _read_existing_cookie_file()
    if not text:
        return False
    try:
        _validate_cookies(text)
        return True
    except ValueError:
        return False


def cookie_file_status() -> str:
    """Return a non-secret diagnostic suitable for logs/health checks."""
    if not COOKIE_PATH.is_file():
        return "missing"
    try:
        text = COOKIE_PATH.read_text(encoding="utf-8", errors="strict")
        _validate_cookies(text)
    except (OSError, UnicodeError):
        return "unreadable"
    except ValueError:
        return "invalid"
    return "valid"


async def fetch_and_store_cookies() -> bool:
    """Load cookies from Base64 or URL; return False when cookies are not configured.

    Missing cookies are intentionally non-fatal because yt-dlp can operate without
    them for many public videos.
    """
    if YTDLP_COOKIES_B64:
        cookies = _validate_cookies(_decode_b64(YTDLP_COOKIES_B64))
        await asyncio.to_thread(_atomic_store, cookies)
        return True

    if COOKIE_URL:
        raw_url = resolve_raw_cookie_url(COOKIE_URL)
        try:
            response = await asyncio.to_thread(
                requests.get,
                raw_url,
                timeout=15,
                headers={"User-Agent": "Trebel-cookie-fetcher/2.0"},
            )
            response.raise_for_status()
            cookies = _validate_cookies(response.text)
        except requests.RequestException as exc:
            # Never replace a known-good local cookie jar with a failed remote
            # fetch. Startup can continue using the existing jar.
            if _existing_cookie_file_is_usable():
                return True
            raise ConnectionError(f"Unable to fetch cookies: {exc}") from exc
        except ValueError:
            # Same safety rule for a URL that returned HTML/JSON or a truncated
            # cookie file instead of a valid Netscape jar.
            if _existing_cookie_file_is_usable():
                return True
            raise
        await asyncio.to_thread(_atomic_store, cookies)
        return True

    return _existing_cookie_file_is_usable()
