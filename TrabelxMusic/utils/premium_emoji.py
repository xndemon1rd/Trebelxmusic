"""Telegram custom/premium emoji helpers.

The IDs are supplied by the bot owner.  We keep normal Unicode fallback
characters in the text and attach Telegram custom-emoji entities so the
message renders as premium emoji when the IDs are valid.
"""
from pyrogram.enums import MessageEntityType
from pyrogram.types import MessageEntity

UNICORN_EMOJI_IDS = (
    "5285238101344544669",  # 📦
    "5292099655197289800",  # ✨
    "5778669091342520121",  # 🇪🇸
    "5287295223175604777",  # ❤️‍🔥 / 💗
    "5246849941350944621",  # 🚧
)

# Backward-compatible name used by the rest of the bot.  All premium/custom
# emoji entities now use the new unicorn emoji set supplied by the owner.
PREMIUM_EMOJI = {
    "unicorn_1": UNICORN_EMOJI_IDS[0],
    "unicorn_2": UNICORN_EMOJI_IDS[1],
    "unicorn_3": UNICORN_EMOJI_IDS[2],
    "unicorn_4": UNICORN_EMOJI_IDS[3],
    "unicorn_5": UNICORN_EMOJI_IDS[4],
}


# Visible fallback -> custom emoji IDs.  The three butterfly IDs are rotated
# so the welcome message can have the supplied unicorn emoji set.
DEFAULT_EMOJI = {
    '🍷': UNICORN_EMOJI_IDS[0],
    '💞': UNICORN_EMOJI_IDS[1],
    '🥃': UNICORN_EMOJI_IDS[2],
    '🤩': UNICORN_EMOJI_IDS[3],
    '🎩': UNICORN_EMOJI_IDS[4],
    '🥂': UNICORN_EMOJI_IDS[0],
    '🪄': UNICORN_EMOJI_IDS[1],
    '🫧': UNICORN_EMOJI_IDS[2],
    '🪽': UNICORN_EMOJI_IDS[3],
    '🕊️': UNICORN_EMOJI_IDS[4],
    '✨': UNICORN_EMOJI_IDS[1],
    '📥': UNICORN_EMOJI_IDS[0],
    '🔗': UNICORN_EMOJI_IDS[2],
    '🧪': UNICORN_EMOJI_IDS[3],
    '🌈': UNICORN_EMOJI_IDS[4],
    '🥀': UNICORN_EMOJI_IDS[0],
    '💌': UNICORN_EMOJI_IDS[1],
    '🧨': UNICORN_EMOJI_IDS[2],
    '🔥': UNICORN_EMOJI_IDS[3],
    '🎙️': UNICORN_EMOJI_IDS[4],
    '📌': UNICORN_EMOJI_IDS[0],
    '📍': UNICORN_EMOJI_IDS[1],
    '👑': UNICORN_EMOJI_IDS[2],
    '🎵': UNICORN_EMOJI_IDS[0],
    '🎶': UNICORN_EMOJI_IDS[1],
    '🎧': UNICORN_EMOJI_IDS[2],
    '🎬': UNICORN_EMOJI_IDS[3],
    '📦': UNICORN_EMOJI_IDS[4],
    '⏳': UNICORN_EMOJI_IDS[0],
    '❌': UNICORN_EMOJI_IDS[1],
    '❗': UNICORN_EMOJI_IDS[2],
    '⚠️': UNICORN_EMOJI_IDS[3],
    '▶️': UNICORN_EMOJI_IDS[4],
    '⏸️': UNICORN_EMOJI_IDS[0],
    '⏹️': UNICORN_EMOJI_IDS[1],
    '⏭️': UNICORN_EMOJI_IDS[2],
    '🔊': UNICORN_EMOJI_IDS[3],
    '🔄': UNICORN_EMOJI_IDS[4],
    '🔍': UNICORN_EMOJI_IDS[0],
    '🪙': UNICORN_EMOJI_IDS[1],
    '💎': UNICORN_EMOJI_IDS[2],
    '⭐': UNICORN_EMOJI_IDS[3],
    '🛍️': UNICORN_EMOJI_IDS[4],
    '📂': UNICORN_EMOJI_IDS[0],
    '📜': UNICORN_EMOJI_IDS[1],
    '➕': UNICORN_EMOJI_IDS[2],
    '✖️': UNICORN_EMOJI_IDS[3],
}

BUTTERFLIES = UNICORN_EMOJI_IDS


def _utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def custom_emoji_entities(text: str, *, butterfly_cycle: bool = True, blockquote: bool = True):
    """Return Pyrogram custom-emoji entities for known visible emoji.

    Telegram message offsets are UTF-16 based, so offsets/lengths are
    calculated in UTF-16 code units rather than Python code points.
    """
    entities = []
    if blockquote and text:
        entities.append(
            MessageEntity(
                type=MessageEntityType.BLOCKQUOTE,
                offset=0,
                length=_utf16_len(text),
            )
        )
    butterfly_index = 0
    cursor = 0

    # Longest visible emoji first (e.g. dove includes a variation selector).
    tokens = sorted(DEFAULT_EMOJI, key=len, reverse=True)
    while cursor < len(text):
        matched = None
        emoji_id = None
        for token in tokens:
            if text.startswith(token, cursor):
                matched = token
                emoji_id = DEFAULT_EMOJI[token]
                break
        if text[cursor] == "🦋":
            matched = "🦋"
            emoji_id = BUTTERFLIES[butterfly_index % len(BUTTERFLIES)] if butterfly_cycle else BUTTERFLIES[0]
            butterfly_index += 1

        if matched:
            before = text[:cursor]
            entities.append(
                MessageEntity(
                    type=MessageEntityType.CUSTOM_EMOJI,
                    offset=_utf16_len(before),
                    length=_utf16_len(matched),
                    custom_emoji_id=emoji_id,
                )
            )
            cursor += len(matched)
        else:
            cursor += 1
    return entities



def install_message_emoji_hooks():
    """Attach configured Telegram custom-emoji entities to normal bot output.

    Existing explicit entities are preserved. The hook covers text and media
    captions, including callback edits, so selected UI areas consistently use
    the configured premium/custom emoji IDs without changing their text.
    """
    try:
        from pyrogram import Client
        from pyrogram.types import Message
    except Exception:
        return
    if getattr(Message, "_trebel_premium_hooks", False):
        return

    def _text_kwargs(args, kwargs):
        if kwargs.get("entities") is not None:
            return
        text = kwargs.get("text")
        if text is None and args and isinstance(args[0], str):
            text = args[0]
        if isinstance(text, str) and text:
            kwargs["entities"] = custom_emoji_entities(text, blockquote=False)

    def _caption_kwargs(args, kwargs):
        if kwargs.get("caption_entities") is not None:
            return
        caption = kwargs.get("caption")
        if isinstance(caption, str) and caption:
            kwargs["caption_entities"] = custom_emoji_entities(caption, blockquote=False)

    def wrap_text(cls, name):
        original = getattr(cls, name, None)
        if original is None or getattr(original, "_trebel_premium_wrapped", False):
            return
        async def wrapped(self, *args, **kwargs):
            _text_kwargs(args, kwargs)
            return await original(self, *args, **kwargs)
        wrapped._trebel_premium_wrapped = True
        setattr(cls, name, wrapped)

    def wrap_caption(cls, name):
        original = getattr(cls, name, None)
        if original is None or getattr(original, "_trebel_premium_wrapped", False):
            return
        async def wrapped(self, *args, **kwargs):
            _caption_kwargs(args, kwargs)
            return await original(self, *args, **kwargs)
        wrapped._trebel_premium_wrapped = True
        setattr(cls, name, wrapped)

    for cls in (Message, Client):
        for name in ("reply_text", "edit_text", "send_message", "edit_message_text"):
            wrap_text(cls, name)
        for name in ("reply_photo", "reply_audio", "reply_video", "reply_document",
                     "edit_caption", "send_photo", "send_audio", "send_video",
                     "send_document", "edit_message_caption"):
            wrap_caption(cls, name)
    Message._trebel_premium_hooks = True
