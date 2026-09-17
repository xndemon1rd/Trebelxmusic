# Authored By Dev © 2025
import asyncio
import time
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from youtubesearchpython.aio import VideosSearch

import config
from TrabelxMusic import app
from TrabelxMusic.misc import _boot_
from TrabelxMusic.plugins.admin.admins import admins_list
from TrabelxMusic.utils import bot_sys_stats
from TrabelxMusic.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    get_served_chats,
    get_served_users,
    is_banned_user,
    is_on_off,
    get_economy,
    claim_daily_reward,
    claim_weekly_reward,
    set_referrer,
)
from TrabelxMusic.utils.decorators.language import LanguageStart
from TrabelxMusic.utils.formatters import get_readable_time
from TrabelxMusic.utils.premium_emoji import custom_emoji_entities
from TrabelxMusic.utils.errors import report_exception
from TrabelxMusic.utils.inline.start import private_panel, start_panel
from TrabelxMusic.utils.inline.help import first_page
from config import BANNED_USERS, HELP_IMG_URL, START_IMG_URL
from strings import get_string


async def delete_sticker_after_delay(message: Message, delay: int) -> None:
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    user_id = message.from_user.id
    try:
        await add_served_user(user_id)
    except Exception:
        pass

    # Referral attribution: the referred user is linked to the person whose
    # deep link they opened. The referrer is rewarded when this user adds the
    # bot to a group.
    if len(message.text.split()) > 1:
        start_arg = message.text.split(None, 1)[1]
        if start_arg.startswith("ref_"):
            try:
                await set_referrer(user_id, int(start_arg.split("_", 1)[1]))
            except (ValueError, TypeError):
                pass

    # Claim login rewards automatically. VIP receives +5%, membership +1%.
    try:
        from datetime import datetime, timezone
        economy = await get_economy(user_id)
        now = datetime.now(timezone.utc)
        bonus = 5 if economy.get("vip_until") and economy["vip_until"] > now else (
            1 if economy.get("membership_until") and economy["membership_until"] > now else 0
        )
        await claim_daily_reward(user_id, int(100 * (100 + bonus) / 100))
        await claim_weekly_reward(user_id, int(300 * (100 + bonus) / 100))
    except Exception:
        pass

    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]

        if name.startswith("help"):
            keyboard = first_page(_)
            return await message.reply_photo(
                photo=HELP_IMG_URL,
                caption=_["help_1"].format(config.SUPPORT_CHAT),
                reply_markup=keyboard,
            )

        if name.startswith("sud"):
            await admins_list(client=client, message=message, _=_)
            if await is_on_off(2):
                username = f"@{message.from_user.username}" if message.from_user.username else "(none)"
                await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=(
                        f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>sᴜᴅᴏʟɪsᴛ</b>.\n\n"
                        f"<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n"
                        f"<b>ᴜsᴇʀɴᴀᴍᴇ :</b> {username}"
                    ),
                )
            return

        if name.startswith("inf"):
            m = await message.reply_text("🔎")
            try:
                vid_id = str(name).replace("info_", "", 1)
                query = f"https://www.youtube.com/watch?v={vid_id}"
                results = VideosSearch(query, limit=1)
                data = await results.next()
                result = (data.get("result") or [None])[0]
                if not result:
                    await m.edit_text("No results found.")
                    return

                title = result.get("title") or "Unknown"
                duration = result.get("duration") or "Unknown"
                views = (result.get("viewCount") or {}).get("short") or "Unknown"
                thumbnail = ((result.get("thumbnails") or [{}])[0].get("url") or "").split("?")[0]
                channellink = (result.get("channel") or {}).get("link") or "https://youtube.com"
                channel = (result.get("channel") or {}).get("name") or "Unknown"
                link = result.get("link") or query
                published = result.get("publishedTime") or "Unknown"

                searched_text = _["start_6"].format(title, duration, views, published, channellink, channel, app.mention)
                key = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text=_["S_B_6"], url=link),
                      InlineKeyboardButton(text=_["S_B_4"], url=config.SUPPORT_CHAT)]]
                )

                await m.delete()

                await app.send_photo(
                    chat_id=message.chat.id,
                    photo=thumbnail or HELP_IMG_URL,
                    caption=searched_text,
                    reply_markup=key,
                )

                if await is_on_off(2):
                    username = f"@{message.from_user.username}" if message.from_user.username else "(none)"
                    await app.send_message(
                        chat_id=config.LOGGER_ID,
                        text=(
                            f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>ᴛʀᴀᴄᴋ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b>.\n\n"
                            f"<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n"
                            f"<b>ᴜsᴇʀɴᴀᴍᴇ :</b> {username}"
                        ),
                    )
            except Exception as e:
                await m.edit_text(f"Error: {e}")
            return

    out = private_panel(_)

    served_chats_coro = get_served_chats()
    served_users_coro = get_served_users()
    stats_coro = bot_sys_stats()
    served_chats, served_users, (UP, CPU, RAM, DISK) = await asyncio.gather(
        served_chats_coro, served_users_coro, stats_coro
    )

    caption = (
        f"╭───────────────────▣\n"
        f"│❍ ʜᴇʏ • {message.from_user.mention}\n"
        f"│❍ ɪ ᴀᴍ <b>{app.mention}</b>\n"
        f"├───────────────────▣\n"
        f"│❍ ʙᴇsᴛ ǫᴜɪʟɪᴛʏ ғᴇᴀᴛᴜʀᴇs •\n"
        f"│❍ sᴛᴀʀᴛ ʏᴏᴜʀ ᴊᴏᴜʀɴᴇʏ ✨\n"
        f"╰───────────────────▣"
    )
    # Use the configured premium/custom emoji entities in private /start.
    # If Telegram rejects an entity, fall back to a normal quoted message.
    try:
        await message.reply_photo(
            photo=START_IMG_URL,
            caption=caption,
            caption_entities=custom_emoji_entities(caption),
            reply_markup=InlineKeyboardMarkup(out),
        )
    except Exception as exc:
        await report_exception(
            exc,
            label="Premium Emoji Rendering Error",
            extras={"Handler": "/start", "Chat ID": message.chat.id},
        )
        await message.reply_photo(
            photo="TrabelxMusic/assets/Trabel/welcome.png",
            caption=f"<blockquote>{caption}</blockquote>",
            reply_markup=InlineKeyboardMarkup(out),
        )

    if await is_on_off(2):
        username = f"@{message.from_user.username}" if message.from_user.username else "(none)"
        await app.send_message(
            chat_id=config.LOGGER_ID,
            text=(
                f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ.\n\n"
                f"<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n"
                f"<b>ᴜsᴇʀɴᴀᴍᴇ :</b> {username}"
            ),
        )


@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    uptime = int(time.time() - _boot_)
    try:
        await message.reply_text(
            (
                f"🎧 <b>{app.mention}</b>\n"
                f"⚡ Online: <b>{get_readable_time(uptime)}</b>\n"
                f"🎵 Play · 📥 Download · 🎬 Audio/Video · 🔗 Direct URLs"
            ),
            reply_markup=InlineKeyboardMarkup(out),
        )
    except Exception as exc:
        await report_exception(
            exc,
            label="Group Start Send Error",
            extras={"Chat ID": message.chat.id},
        )
    return await add_served_chat(message.chat.id)


@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)

            if await is_banned_user(member.id):
                try:
                    await message.chat.ban_member(member.id)
                except Exception:
                    pass

            if member.id == app.id:
                if message.chat.type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_4"])
                    return await app.leave_chat(message.chat.id)

                if message.chat.id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_5"].format(
                            app.mention,
                            f"https://t.me/{app.username}?start=adminlist",
                            config.SUPPORT_CHAT,
                        ),
                        disable_web_page_preview=True,
                    )
                    return await app.leave_chat(message.chat.id)

                out = start_panel(_)
                await message.reply_text(
                    (
                        f"🕊️ <b>Peace & Music • {message.chat.title}</b>\n\n"
                        f"🌿 Hello everyone, I’m <b>{app.mention}</b>."
                        " I’m here to keep your group peaceful, musical and easy to enjoy.\n\n"
                        f"🎶 <b>Play:</b> /play <code>song or URL</code>\n"
                        f"📥 <b>Download:</b> /download <code>URL</code>\n"
                        f"📚 <b>Commands:</b> /help\n\n"
                        "🤍 Be kind, enjoy the music, and let the good vibes stay."
                    ),
                    reply_markup=InlineKeyboardMarkup(out),
                )
                await add_served_chat(message.chat.id)
                await message.stop_propagation()

        except Exception as ex:
            await report_exception(
                ex,
                label="Welcome Handler Error",
                extras={"Chat ID": message.chat.id, "Chat": message.chat.title or "N/A"},
            )
