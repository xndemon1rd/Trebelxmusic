# Authored By Dev © 2025
import sys
from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message

import config
from ..logging import LOGGER


# Compatibility shim for legacy Pyrogram-style ``quote=`` calls. Kurigram
# does not accept ``quote`` on Message.reply* methods; when a plugin passes it,
# translate quote=True to the portable reply_to_message_id argument instead.
def _install_reply_compatibility():
    method_names = (
        "reply", "reply_text", "reply_photo", "reply_audio", "reply_video",
        "reply_animation", "reply_document", "reply_voice", "reply_sticker",
        "reply_media_group", "reply_location", "reply_contact", "reply_poll",
        "reply_dice", "reply_venue",
    )
    for method_name in method_names:
        original = getattr(Message, method_name, None)
        if original is None or getattr(original, "_trebel_reply_compat", False):
            continue

        async def compatible(self, *args, __original=original, **kwargs):
            if "quote" in kwargs:
                quote = kwargs.pop("quote")
                if quote and "reply_to_message_id" not in kwargs:
                    kwargs["reply_to_message_id"] = self.id
            if "disable_web_page_preview" in kwargs:
                disabled = kwargs.pop("disable_web_page_preview")
                if disabled and "link_preview_options" not in kwargs:
                    try:
                        from pyrogram.types import LinkPreviewOptions
                        kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
                    except Exception:
                        pass
            return await __original(self, *args, **kwargs)

        compatible._trebel_reply_compat = True
        setattr(Message, method_name, compatible)


def _install_client_preview_compatibility():
    # Client-level calls such as app.send_message() also used the legacy
    # disable_web_page_preview flag in older plugins.
    for method_name in ("send_message", "edit_message_text", "edit_message_caption"):
        original = getattr(Client, method_name, None)
        if original is None or getattr(original, "_trebel_preview_compat", False):
            continue

        async def compatible_client(self, *args, __original=original, **kwargs):
            if "disable_web_page_preview" in kwargs:
                disabled = kwargs.pop("disable_web_page_preview")
                if disabled and "link_preview_options" not in kwargs:
                    try:
                        from pyrogram.types import LinkPreviewOptions
                        kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
                    except Exception:
                        pass
            return await __original(self, *args, **kwargs)

        compatible_client._trebel_preview_compat = True
        setattr(Client, method_name, compatible_client)


_install_reply_compatibility()
_install_client_preview_compatibility()

class MusicBotClient(Client):
    def __init__(self):
        super().__init__(
            name="TrabelxMusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            workers=48,
            max_concurrent_transmissions=7,
        )
        LOGGER(__name__).info("Bot client initialized.")

    def add_handler(self, handler, group=0):
        """Wrap every un-decorated Pyrogram handler so exceptions reach LOGGER GC."""
        callback = getattr(handler, "callback", None)
        if callback and not getattr(callback, "_trabel_error_capture", False) and not getattr(callback, "_trabel_global_capture", False):
            async def guarded(client, *args, __callback=callback, **kwargs):
                try:
                    return await __callback(client, *args, **kwargs)
                except Exception as exc:
                    from TrabelxMusic.utils.errors import report_exception
                    obj = args[0] if args else None
                    chat = getattr(getattr(obj, "chat", None), "id", "N/A")
                    user = getattr(getattr(obj, "from_user", None), "id", "N/A")
                    label = "Callback Handler Error" if obj and obj.__class__.__name__ == "CallbackQuery" else "Message Handler Error"
                    await report_exception(exc, label=label, extras={"Handler": getattr(__callback, "__name__", "unknown"), "Chat ID": chat, "User ID": user})
                    raise
            guarded._trabel_global_capture = True
            handler.callback = guarded
        return super().add_handler(handler, group)

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username, self.id = me.username, me.id
        self.name = f"{me.first_name} {me.last_name or ''}".strip()
        self.mention = me.mention

        try:
            await self.send_message(
                config.LOGGER_ID,
                (
                    f"<u><b>» {self.mention} ʙᴏᴛ sᴛᴀʀᴛᴇᴅ :</b></u>\n\n"
                    f"ɪᴅ : <code>{self.id}</code>\n"
                    f"ɴᴀᴍᴇ : {self.name}\n"
                    f"ᴜsᴇʀɴᴀᴍᴇ : @{self.username}"
                ),
            )
        except (errors.ChannelInvalid, errors.PeerIdInvalid):
            LOGGER(__name__).error("❌ Bot cannot access the log group/channel – add & promote it first!")
            sys.exit()
        except Exception as exc:
            LOGGER(__name__).error(f"❌ Bot has failed to access the log group.\nReason: {type(exc).__name__}")
            sys.exit()

        try:
            member = await self.get_chat_member(config.LOGGER_ID, self.id)
            if member.status != ChatMemberStatus.ADMINISTRATOR:
                LOGGER(__name__).error("❌ Promote the bot as admin in the log group/channel.")
                sys.exit()
        except Exception as e:
            LOGGER(__name__).error(f"❌ Could not check admin status: {e}")
            sys.exit()

        LOGGER(__name__).info(f"✅ Music Bot started as {self.name} (@{self.username})")
