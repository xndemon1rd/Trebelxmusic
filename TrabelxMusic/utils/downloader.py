# Authored By Certified Coders © 2025
import asyncio
import contextlib
import glob
import os
import re
import mimetypes
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

from TrabelxMusic.core.dir import CACHE_DIR, DOWNLOAD_DIR
from TrabelxMusic.utils.cookie_handler import COOKIE_PATH as _COOKIES_FILE
from TrabelxMusic.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL, VIDEO_API_URL
from TrabelxMusic.logging import LOGGER

LOGGER = LOGGER(__name__)

USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def log_download_source(title: str, source: str) -> None:
    LOGGER.info(f"Track '{title}' - Downloaded by {source}")


def extract_video_id(link: str) -> str:
    if not link:
        return ""
    s = link.strip()
    if YOUTUBE_ID_RE.match(s):
        return s
    if "v=" in s:
        return s.split("v=")[-1].split("&")[0]
    last = s.split("/")[-1].split("?")[0]
    if YOUTUBE_ID_RE.match(last):
        return last
    return ""


def get_cookie_file() -> Optional[str]:
    try:
        if _COOKIES_FILE and os.path.exists(_COOKIES_FILE) and os.path.getsize(_COOKIES_FILE) > 0:
            return _COOKIES_FILE
    except Exception:
        pass
    return None


def find_cached_file(video_id: str) -> Optional[str]:
    if not video_id:
        return None
    for ext in ("mp3", "m4a", "webm", "mp4", "mkv"):
        path = f"{DOWNLOAD_DIR}/{video_id}.{ext}"
        if os.path.exists(path):
            return path
    return None


def get_ytdlp_base_opts() -> Dict[str, object]:
    opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": False,
        "continuedl": True,
        "noprogress": True,
        "concurrent_fragment_downloads": 16,
        "http_chunk_size": 1 << 20,
        "socket_timeout": 15,
        "retries": 1,
        "fragment_retries": 1,
        "cachedir": str(CACHE_DIR),
        "ignoreerrors": True,
        "merge_output_format": "mp4"
    }
    if cookiefile := get_cookie_file():
        opts["cookiefile"] = cookiefile
    return opts


async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        timeout = aiohttp.ClientTimeout(total=600, sock_connect=20, sock_read=60)
        connector = TCPConnector(limit=0, ttl_dns_cache=300, enable_cleanup_closed=True)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session


async def close_http_session() -> None:
    global _session
    async with _session_lock:
        if _session and not _session.closed:
            await _session.close()
        _session = None


async def download_file(url: str, out_path: str) -> Optional[str]:
    if not url:
        return None
    try:
        session = await get_http_session()
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if not chunk:
                        break
                    await f.write(chunk)
        return out_path if os.path.exists(out_path) else None
    except Exception:
        return None


async def api_download_audio(link: str) -> Optional[str]:
    if not USE_AUDIO_API:
        return None
    vid = extract_video_id(link)
    if not vid:
        return None
    poll_url = f"{API_URL}/song/{vid}?api={API_KEY}"
    try:
        session = await get_http_session()
        while True:
            async with session.get(poll_url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                status = str(data.get("status", "")).lower()
                if status == "downloading":
                    await asyncio.sleep(1.0)
                    continue
                if status != "done":
                    return None
                dl_url = data.get("link")
                fmt = data.get("format", "webm")
                out_path = f"{DOWNLOAD_DIR}/{vid}.{fmt}"
                return await download_file(dl_url, out_path)
    except Exception:
        return None


async def api_download_video(link: str) -> Optional[str]:
    if not USE_VIDEO_API:
        return None
    vid = extract_video_id(link)
    if not vid:
        return None
    poll_url = f"{VIDEO_API_URL}/video/{vid}?api={API_KEY}"
    try:
        session = await get_http_session()
        while True:
            async with session.get(poll_url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                status = str(data.get("status", "")).lower()
                if status == "downloading":
                    await asyncio.sleep(1.0)
                    continue
                if status != "done":
                    return None
                dl_url = data.get("link")
                fmt = data.get("format", "mp4")
                out_path = f"{DOWNLOAD_DIR}/{vid}.{fmt}"
                return await download_file(dl_url, out_path)
    except Exception:
        return None


def get_final_path_from_info(info: Dict) -> Optional[str]:
    vid = info.get("id")
    if not vid:
        return None
    ext = info.get("ext")
    if ext:
        p = f"{DOWNLOAD_DIR}/{vid}.{ext}"
        if os.path.exists(p):
            return p
    matches = sorted(
        glob.glob(f"{DOWNLOAD_DIR}/{vid}.*"),
        key=os.path.getmtime,
        reverse=True,
    )
    return matches[0] if matches else None


def download_with_ytdlp_sync(link: str, fmt: str) -> Optional[str]:
    """Download a URL and return the actual output path.

    The old implementation checked the filesystem *before* downloading and
    then reused the pre-download metadata object. That made fresh downloads
    frequently return None, which later propagated into MediaStream.
    """
    try:
        opts = get_ytdlp_base_opts()
        opts["format"] = fmt
        # Do not let yt-dlp silently swallow an extractor failure.
        opts["ignoreerrors"] = False
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=True)
            if not info:
                return None
            return get_final_path_from_info(info)
    except Exception as exc:
        LOGGER.warning(f"yt-dlp download failed for {link!r}: {exc}")
        return None


def _safe_filename(value: str, fallback: str = "media") -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._")
    return (value[:120] or fallback)


async def download_direct_url(url: str, media_type: str = "auto") -> Optional[str]:
    """Fallback for direct HTTP media URLs that yt-dlp does not extract."""
    if not url or not url.lower().startswith(("http://", "https://")):
        return None
    try:
        session = await get_http_session()
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status != 200:
                return None
            content_type = (resp.headers.get("Content-Type") or "").split(";", 1)[0].lower()
            if media_type == "audio" and not (content_type.startswith("audio/") or "audio" in content_type):
                return None
            if media_type == "video" and not (content_type.startswith("video/") or "video" in content_type):
                return None
            if media_type == "auto" and not (content_type.startswith("audio/") or content_type.startswith("video/")):
                return None

            ext = Path(urlparse(str(resp.url)).path).suffix.lower()
            if not ext:
                ext = mimetypes.guess_extension(content_type) or ".bin"
            if ext == ".jpe" and media_type == "video":
                return None
            name = _safe_filename(Path(urlparse(str(resp.url)).path).stem, "media")
            out_path = os.path.join(DOWNLOAD_DIR, f"{name}_{int(asyncio.get_running_loop().time() * 1000)}{ext}")
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if chunk:
                        await f.write(chunk)
            return out_path if os.path.exists(out_path) and os.path.getsize(out_path) else None
    except Exception as exc:
        LOGGER.debug(f"Direct media download failed: {exc}")
        return None


async def run_with_semaphore(coro):
    async with SEM:
        return await coro


async def deduplicate_download(key: str, runner):
    async with _inflight_lock:
        if fut := _inflight.get(key):
            return await fut
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    try:
        result = await runner()
        fut.set_result(result)
        return result
    except Exception as e:
        fut.set_exception(e)
        return None
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)


async def race_ytdlp_and_api(yt_task, api_task, title: str):
    done, pending = await asyncio.wait(
        {yt_task, api_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for task in done:
        result = task.result()
        if result and os.path.exists(result):
            source = "yt-dlp" if task is yt_task else "API"
            log_download_source(title, source)
            for p in pending:
                p.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await p
            return result
    for task in pending:
        try:
            result = await task
            if result and os.path.exists(result):
                source = "yt-dlp" if task is yt_task else "API"
                log_download_source(title, source)
                return result
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    return None


async def yt_dlp_download(link: str, type: str, title: str = "") -> Optional[str]:
    loop = asyncio.get_running_loop()
    vid = extract_video_id(link)
    if cached := find_cached_file(vid):
        if title:
            LOGGER.info(f"Track '{title}' - Served from cache")
        return cached

    if type == "audio":
        key = f"audio:{link}"

        async def run():
            ytdlp_task = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(None, download_with_ytdlp_sync, link, "bestaudio/best")
                )
            )
            api_task = asyncio.create_task(api_download_audio(link)) if USE_AUDIO_API else None
            if api_task:
                return await race_ytdlp_and_api(ytdlp_task, api_task, title or "Unknown")
            result = await ytdlp_task
            if result and title:
                log_download_source(title, "yt-dlp")
            return result

        return await deduplicate_download(key, run)

    elif type == "video":
        key = f"video:{link}"

        async def run():
            ytdlp_task = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(None, download_with_ytdlp_sync, link, "bestvideo[height<=720][width<=1280]+bestaudio/best[height<=720]")
                )
            )
            api_task = asyncio.create_task(api_download_video(link)) if USE_VIDEO_API else None
            if api_task:
                return await race_ytdlp_and_api(ytdlp_task, api_task, title or "Unknown")
            result = await ytdlp_task
            if result and title:
                log_download_source(title, "yt-dlp")
            return result

        return await deduplicate_download(key, run)

    return None
