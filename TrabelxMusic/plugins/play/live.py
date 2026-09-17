# Authored By Dev © 2025
import random
from pyrogram import filters

from TrabelxMusic import YouTube, app
from TrabelxMusic.utils.channelplay import get_channeplayCB
from TrabelxMusic.utils.decorators.language import languageCB
from TrabelxMusic.utils.errors import capture_callback_err
from TrabelxMusic.utils.logger import report_play_error
from TrabelxMusic.utils.stream.stream import stream
from config import AYU, BANNED_USERS


@app.on_callback_query(filters.regex("LiveStream") & ~BANNED_USERS)
@languageCB
@capture_callback_err
async def play_live_stream(client, CallbackQuery, _):
    data = CallbackQuery.data.strip().split(None, 1)[1]
    vidid, user_id, mode, cplay, fplay = data.split("|")

    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except Exception:
            return

    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except Exception:
        return

    is_video = (mode == "v")
    forceplay = (fplay == "f")
    user_name = CallbackQuery.from_user.first_name

    try:
        await CallbackQuery.message.delete()
    except Exception:
        pass
    try:
        await CallbackQuery.answer()
    except Exception:
        pass

    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else random.choice(AYU)
    )

    try:
        details, track_id = await YouTube.track("", videoid=vidid)
    except Exception as e:
        await report_play_error(CallbackQuery.message, e, operation="live stream lookup")
        return

    if not details.get("duration_min"):
        try:
            await stream(
                _,
                mystic,
                int(user_id),
                details,
                chat_id,
                user_name,
                CallbackQuery.message.chat.id,
                is_video,
                streamtype="live",
                forceplay=forceplay,
            )
        except Exception as e:
            await report_play_error(CallbackQuery.message, e, operation="live stream playback")
            return
    else:
        return await mystic.edit_text("» ɴᴏᴛ ᴀ ʟɪᴠᴇ sᴛʀᴇᴀᴍ.")

    await mystic.delete()
