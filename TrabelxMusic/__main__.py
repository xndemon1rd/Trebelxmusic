# Authored By Dev © 2025
import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from TrabelxMusic import LOGGER, app, userbot
from TrabelxMusic.core.call import StreamController
from TrabelxMusic.misc import admin
from TrabelxMusic.plugins import ALL_MODULES
from TrabelxMusic.utils.database import get_banned_users, get_gbanned
from TrabelxMusic.utils.cookie_handler import fetch_and_store_cookies
from TrabelxMusic.utils.storage_guard import storage_maintenance_loop
from config import BANNED_USERS, STARTUP_VOICE_CHECK
from TrabelxMusic.utils.errors import install_global_error_logging


async def init():
    # Install global error detection before starting Telegram clients.
    install_global_error_logging()
    try:
        from TrabelxMusic.utils.error_detector import install as install_error_detector
        install_error_detector()
    except Exception as exc:
        LOGGER("TrabelxMusic").warning(f"Self-healing error detector could not start: {exc}")
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("ᴀssɪsᴛᴀɴᴛ sᴇssɪᴏɴ ɴᴏᴛ ғɪʟʟᴇᴅ, ᴘʟᴇᴀsᴇ ғɪʟʟ ᴀ ᴘʏʀᴏɢʀᴀᴍ sᴇssɪᴏɴ...")
        exit()

    await admin()

    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except Exception:
        pass

    await app.start()

    # Cookies are optional. Base64 (YTDLP_COOKIES_B64) is preferred; COOKIE_URL
    # remains supported for backwards compatibility. A missing cookie source must
    # never turn into an internal error or prevent the bot from starting.
    try:
        cookies_loaded = await fetch_and_store_cookies()
        if cookies_loaded:
            LOGGER("TrabelxMusic").info("ʏᴏᴜᴛᴜʙᴇ ᴄᴏᴏᴋɪᴇs ʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ✅")
        else:
            LOGGER("TrabelxMusic").info("ʏᴏᴜᴛᴜʙᴇ ᴄᴏᴏᴋɪᴇs ɴᴏᴛ ᴄᴏɴғɪɢᴜʀᴇᴅ; continuing without cookies.")
    except Exception as e:
        LOGGER("TrabelxMusic").warning(f"⚠️ ᴄᴏᴏᴋɪᴇ ʟᴏᴀᴅ ғᴀɪʟᴇᴅ; continuing without cookies: {type(e).__name__}: {e}")

    for all_module in ALL_MODULES:
        importlib.import_module("TrabelxMusic.plugins" + all_module)

    LOGGER("TrabelxMusic.plugins").info("Trabel modules loaded...")

    await userbot.start()
    await StreamController.start()

    # Do not make startup depend on a third-party sample URL or on an active
    # voice chat in LOGGER_ID. Playback is validated when a real /play starts.
    # Set STARTUP_VOICE_CHECK=true if you explicitly want the legacy probe.
    if STARTUP_VOICE_CHECK:
        try:
            await StreamController.stream_call("https://files.catbox.moe/6d0ejr.mp4")
        except NoActiveGroupCall:
            LOGGER("TrabelxMusic").warning(
                "Startup voice-chat check found no active call in LOGGER_ID; continuing because STARTUP_VOICE_CHECK is enabled."
            )
        except Exception as exc:
            LOGGER("TrabelxMusic").warning(f"Startup voice-chat check failed: {type(exc).__name__}: {exc}")

    await StreamController.decorators()
    storage_task = asyncio.create_task(storage_maintenance_loop())
    LOGGER("TrabelxMusic").info(
        "Trabelx Music Robot Started Successfully..."
    )
    try:
        await idle()
    finally:
        storage_task.cancel()
        try:
            await storage_task
        except asyncio.CancelledError:
            pass
        try:
            from TrabelxMusic.utils.downloader import close_http_session
            await close_http_session()
        except Exception:
            pass
        await app.stop()
        await userbot.stop()
        LOGGER("TrabelxMusic").info("stopping Trabel music bot ...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
