"""/ai text assistant and /cimage AI image generation."""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from html import escape

from pyrogram import filters
from pyrogram.types import Message

from TrabelxMusic import app
from TrabelxMusic.utils.ai import ask, generate_image
from config import BANNED_USERS

_HISTORY = defaultdict(lambda: deque(maxlen=8))


def _prompt(message: Message) -> str:
    text = message.text or message.caption or ""
    parts = text.split(maxsplit=1)
    if len(parts) > 1:
        return parts[1].strip()
    return ""


@app.on_message(filters.command("ai") & ~BANNED_USERS)
async def ai_command(_, message: Message):
    prompt = _prompt(message)
    if not prompt and message.reply_to_message:
        prompt = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not prompt:
        return await message.reply_text("🤖 <b>Trabelx AI</b>\n\nUse <code>/ai your question</code>.")
    status = await message.reply_text("🤖 Thinking…")
    history = list(_HISTORY[message.from_user.id])
    answer = await ask(prompt, history)
    _HISTORY[message.from_user.id].append({"role": "user", "content": prompt})
    _HISTORY[message.from_user.id].append({"role": "assistant", "content": answer[:4000]})
    await status.edit_text(f"🤖 <b>Trabelx AI</b>\n\n{escape(answer[:4000])}")


@app.on_message(filters.command("cimage") & ~BANNED_USERS)
async def cimage_command(_, message: Message):
    prompt = _prompt(message)
    if not prompt:
        return await message.reply_text("🎨 Use <code>/cimage your image prompt</code>.")
    status = await message.reply_text("🎨 Creating your image…")
    path = await generate_image(prompt)
    if not path or not Path(path).exists():
        return await status.edit_text("❌ Image generation failed. Add GEMINI_API_KEY or GROQ_API_KEY for free text AI. /cimage still requires OPENAI_API_KEY.")
    try:
        await message.reply_photo(path, caption=f"🎨 <b>Created by Trabelx AI</b>\n\n{prompt[:700]}")
        await status.delete()
    finally:
        Path(path).unlink(missing_ok=True)
