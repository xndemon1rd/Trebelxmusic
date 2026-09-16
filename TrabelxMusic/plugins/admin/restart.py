# Authored By Certified Coders © 2025
import asyncio
import os
import shutil
import socket
import sys
from datetime import datetime

import urllib3
from pyrogram import filters

import config
from TrabelxMusic import app
from TrabelxMusic.misc import HAPP, ADMINS, XCB
from TrabelxMusic.utils.database import (
    get_active_chats,
    remove_active_chat,
    remove_active_video_chat,
)
from TrabelxMusic.utils.decorators.language import language
from TrabelxMusic.utils.pastebin import ANNIEBIN

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

async def is_heroku():
    return "heroku" in socket.getfqdn()

def cleanup_storage():
    folders_to_remove = ["downloads", "raw_files", "cache"]
    for folder in folders_to_remove:
        try:
            shutil.rmtree(folder)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[CLEANUP] Failed to delete {folder}: {e}")

    for root, dirs, files in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                try:
                    shutil.rmtree(os.path.join(root, d))
                except:
                    pass


@app.on_message(filters.command(["getlog", "logs", "getlogs"]) & ADMINS)
@language
async def log_(client, message, _):
    try:
        await message.reply_document(document="log.txt")
    except:
        await message.reply_text(_["server_1"])


@app.on_message(filters.command(["update", "gitpull"]) & ADMINS)
@language
async def update_(client, message, _):
    if await is_heroku():
        if HAPP is None:
            return await message.reply_text(_["server_2"])

    response = await message.reply_text(_["server_3"])
async def restart_(_, message):
    response = await message.reply_text("ʀᴇsᴛᴀʀᴛɪɴɢ...")
    ac_chats = await get_active_chats()
    for x in ac_chats:
        try:
            await app.send_message(
                chat_id=int(x),
                text=f"{app.mention} ɪs ʀᴇsᴛᴀʀᴛɪɴɢ...\n\nʏᴏᴜ ᴄᴀɴ sᴛᴀʀᴛ ᴩʟᴀʏɪɴɢ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 15-20 sᴇᴄᴏɴᴅs.",
            )
            await remove_active_chat(x)
            await remove_active_video_chat(x)
        except:
            pass

    cleanup_storage()

    await response.edit_text(
        "» ʀᴇsᴛᴀʀᴛ ᴘʀᴏᴄᴇss sᴛᴀʀᴛᴇᴅ, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ ғᴇᴡ sᴇᴄᴏɴᴅs ᴜɴᴛɪʟ ᴛʜᴇ ʙᴏᴛ sᴛᴀʀᴛs..."
    )

    os.execv(sys.executable, [sys.executable, "-m", "TrabelxMusic"])
