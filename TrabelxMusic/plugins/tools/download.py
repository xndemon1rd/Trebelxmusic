# Universal media downloader for TrabelxMusic.
import re
import time
from pathlib import Path

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

from config import BANNED_USERS, OWNER_ID
EXTRA_DOWNLOAD_COST = int(getattr(__import__('config'), 'DOWNLOAD_EXTRA_COST_COINS', 100))
from TrabelxMusic import app
from TrabelxMusic.utils.downloader import download_direct_url, yt_dlp_download
from TrabelxMusic.utils.database import consume_download, refund_download, buy_extra_download, get_download_status, get_coins
from TrabelxMusic.utils.errors import capture_err, capture_callback_err, report_exception

_PENDING = {}
_PENDING_TTL = 900
_URL_RE = re.compile(r"https?://[^\s<>]+", re.I)


def _extract_url(message: Message):
    text = message.text or message.caption or ""
    found = _URL_RE.search(text)
    if found:
        return found.group(0).rstrip(".,)>]")
    reply = message.reply_to_message
    if reply:
        text = reply.text or reply.caption or ""
        found = _URL_RE.search(text)
        if found:
            return found.group(0).rstrip(".,)>]")
        # Telegram media messages can expose a direct file URL only through
        # their download API, so those are intentionally handled separately.
    return None


def _remember(user_id: int, url: str) -> str:
    token = f"{user_id:x}{int(time.time() * 1000):x}"[-32:]
    _PENDING[token] = (user_id, url, time.time())
    # Small opportunistic cleanup.
    now = time.time()
    for key, (_, _, created) in list(_PENDING.items()):
        if now - created > _PENDING_TTL:
            _PENDING.pop(key, None)
    return token


def _buttons(token: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎧 Audio", callback_data=f"universal_dl|{token}|a"),
            InlineKeyboardButton("🎬 Video", callback_data=f"universal_dl|{token}|v"),
            InlineKeyboardButton("📦 File", callback_data=f"universal_dl|{token}|f"),
        ],
        [InlineKeyboardButton("✖️ Cancel", callback_data=f"universal_dl|{token}|x")],
    ])


@app.on_message(filters.command("download") & ~BANNED_USERS)
@capture_err
async def universal_download_command(_, message: Message):
    url = _extract_url(message)
    if not url:
        return await message.reply_text(
            "📥 <b>Universal Download</b>\n\nSend <code>/download URL</code> or reply to a message containing a URL.\n\nSupports any source that yt-dlp can extract, plus direct HTTP audio/video files."
        )
    token = _remember(message.from_user.id, url)
    return await message.reply_text(
        f"📥 <b>Download ready</b>\n\n🔗 <code>{url[:900]}</code>\n\nChoose the format:",
        reply_markup=_buttons(token),
        disable_web_page_preview=True,
    )


@app.on_callback_query(filters.regex(r"^universal_dl\|") & ~BANNED_USERS)
@capture_callback_err
async def universal_download_callback(_, query: CallbackQuery):
    parts = query.data.split("|")
    if len(parts) != 3:
        return await query.answer("Invalid request.", show_alert=True)
    _, token, mode = parts
    item = _PENDING.get(token)
    if not item:
        return await query.answer("This download request expired. Send /download again.", show_alert=True)
    user_id, url, created = item
    if query.from_user.id != user_id:
        return await query.answer("This download menu belongs to another user.", show_alert=True)
    if time.time() - created > _PENDING_TTL:
        _PENDING.pop(token, None)
        return await query.answer("This request expired.", show_alert=True)
    if mode == "x":
        _PENDING.pop(token, None)
        await query.answer("Cancelled")
        return await query.message.edit_text("✖️ Download cancelled.")

    # Enforce the daily download allowance at the point of actual download.
    allowed, status = await consume_download(user_id)
    if not allowed:
        coins = await get_coins(user_id)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"➕ +1 download · {EXTRA_DOWNLOAD_COST} 🪙",
                callback_data=f"download_buy_extra|{token}|{mode}",
            )],
            [InlineKeyboardButton("🛍 Store", callback_data="eco:store")],
        ])
        return await query.message.edit_text(
            f"📥 <b>Daily download limit reached</b>\n\n"
            f"Used: <b>{status['used']}/{status['limit']}</b>\n"
            f"Extra downloads: <b>{status.get('extra', 0)}</b>\n"
            f"Balance: <b>{coins:,} 🪙</b>\n\n"
            f"Buy one extra download for <b>{EXTRA_DOWNLOAD_COST} coins</b>, or upgrade to Membership/VIP.",
            reply_markup=kb,
        )

    await query.answer("Starting download…")
    await query.message.edit_text(
        "⏳ <b>Downloading…</b>\n\n🔗 <code>" + url[:900] + "</code>",
        disable_web_page_preview=True,
    )
    media_type = "audio" if mode == "a" else "video" if mode == "v" else "file"

    path = await yt_dlp_download(url, type=media_type)
    if not path:
        path = await download_direct_url(url, media_type)
    extra_used = bool(status.get("extra_used"))
    if not path or not Path(path).exists():
        await refund_download(user_id, extra_used=extra_used)
        await report_exception(RuntimeError("Universal download produced no usable file"), label="Universal Download Error", extras={"URL": url, "User ID": user_id, "Media Type": media_type})
        _PENDING.pop(token, None)
        return await query.message.edit_text("❌ <b>Download failed.</b>\n\nThe reserved download has been returned. The source may be unsupported, unavailable, protected, or require authentication.")

    delivered = False
    try:
        if media_type == "audio":
            await query.message.reply_audio(path, caption="🎧 <b>Download complete</b>")
        elif media_type == "video":
            await query.message.reply_video(path, caption="🎬 <b>Download complete</b>", supports_streaming=True)
        else:
            await query.message.reply_document(path, caption="📦 <b>Download complete</b>")
        delivered = True
        await query.message.delete()
    except Exception as exc:
        if not delivered:
            await refund_download(user_id, extra_used=extra_used)
        try:
            await query.message.edit_text(f"❌ <b>Upload failed.</b>\n\n<code>{type(exc).__name__}</code>\nThe reserved download was returned.")
        except Exception:
            pass
    finally:
        _PENDING.pop(token, None)
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass


@app.on_callback_query(filters.regex(r"^download_buy_extra\|") & ~BANNED_USERS)
@capture_callback_err
async def download_buy_extra_callback(_, query: CallbackQuery):
    parts = query.data.split("|")
    if len(parts) != 3:
        return await query.answer("Invalid request.", show_alert=True)
    _, token, mode = parts
    item = _PENDING.get(token)
    if not item:
        return await query.answer("This download request expired.", show_alert=True)
    user_id, url, created = item
    if query.from_user.id != user_id:
        return await query.answer("This menu belongs to another user.", show_alert=True)
    if mode not in ("a", "v", "f"):
        return await query.answer("Invalid media type.", show_alert=True)

    if not await buy_extra_download(user_id, EXTRA_DOWNLOAD_COST):
        return await query.answer(
            f"You need {EXTRA_DOWNLOAD_COST} coins for one extra download.",
            show_alert=True,
        )

    allowed, status = await consume_download(user_id)
    if not allowed:
        return await query.answer("Could not reserve the extra download. Try again.", show_alert=True)

    await query.answer("Extra download purchased.")
    await query.message.edit_text(
        "⏳ <b>Downloading your extra download…</b>\n\n🔗 <code>" + url[:900] + "</code>",
        disable_web_page_preview=True,
    )
    media_type = "audio" if mode == "a" else "video" if mode == "v" else "file"
    path = await yt_dlp_download(url, type=media_type)
    if not path:
        path = await download_direct_url(url, media_type)
    extra_used = bool(status.get("extra_used"))
    if not path or not Path(path).exists():
        await refund_download(user_id, extra_used=extra_used)
        await report_exception(RuntimeError("Extra universal download produced no usable file"), label="Extra Download Error", extras={"URL": url, "User ID": user_id, "Media Type": media_type})
        return await query.message.edit_text(
            "❌ <b>Download failed.</b>\n\n"
            "Your reserved download was returned. Please try another source."
        )
    delivered = False
    try:
        if media_type == "audio":
            await query.message.reply_audio(path, caption="🎧 <b>Download complete</b>")
        elif media_type == "video":
            await query.message.reply_video(path, caption="🎬 <b>Download complete</b>", supports_streaming=True)
        else:
            await query.message.reply_document(path, caption="📦 <b>Download complete</b>")
        delivered = True
        await query.message.delete()
    except Exception as exc:
        if not delivered:
            await refund_download(user_id, extra_used=extra_used)
        try:
            await query.message.edit_text(f"❌ <b>Upload failed.</b>\n\n<code>{type(exc).__name__}</code>\nThe reserved download was returned.")
        except Exception:
            pass
    finally:
        _PENDING.pop(token, None)
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass
