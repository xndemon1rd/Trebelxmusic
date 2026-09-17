"""User profile, history, personal playlists and lyrics."""
from __future__ import annotations
import asyncio
import html
import re
from urllib.parse import quote_plus
import aiohttp
from pyrogram import filters
from pyrogram.types import Message
from TrabelxMusic import app, YouTube
from TrabelxMusic.utils.database import get_song_history, create_user_playlist, get_user_playlists, get_user_playlist, add_user_playlist_track, remove_user_playlist_track, delete_user_playlist
from TrabelxMusic.utils.errors import capture_err
from TrabelxMusic.utils.stream.stream import stream
from config import BANNED_USERS

async def _target(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if len(message.command) > 1:
        try: return await app.get_users(int(message.command[1]))
        except Exception:
            try: return await app.get_users(message.command[1].lstrip('@'))
            except Exception: pass
    return message.from_user

@app.on_message(filters.command("check") & ~BANNED_USERS)
@capture_err
async def check_bot(_, message: Message):
    me = await app.get_me()
    text = ("🤖 <b>TrabelxMusic Bot Profile</b>\n\n"
            f"👤 Name: <b>{html.escape(me.first_name or 'TrabelxMusic')}</b>\n"
            f"🔗 Username: <code>@{me.username or '—'}</code>\n"
            f"🆔 ID: <code>{me.id}</code>\n"
            f"📡 DC: <code>{getattr(me, 'dc_id', '—')}</code>\n\n"
            "🎵 Music • 📥 Universal Download • 👑 VIP • 💎 Membership • 🪙 Economy • 🤖 AI")
    await message.reply_text(text)

@app.on_message(filters.command(["history", "myhistory"]) & ~BANNED_USERS)
@capture_err
async def history_command(_, message: Message):
    rows = await get_song_history(message.from_user.id, 20)
    if not rows:
        return await message.reply_text("📜 <b>Song History</b>\n\nNo songs played yet.")
    lines = []
    for i, row in enumerate(rows, 1):
        title = html.escape(row.get('title','—')[:90])
        lines.append(f"{i}. {title}")
    await message.reply_text("📜 <b>Your Song History</b>\n\n" + "\n".join(lines))

@app.on_message(filters.command("playlist") & ~BANNED_USERS)
@capture_err
async def playlist_command(_, message: Message):
    args = message.text.split(maxsplit=3)
    if len(args) < 2:
        return await message.reply_text("📂 <b>Playlist</b>\n\n<code>/playlist create NAME</code>\n<code>/playlist add NAME SONG</code>\n<code>/playlist show NAME</code>\n<code>/playlist play NAME</code>\n<code>/playlist remove NAME NUMBER</code>\n<code>/playlist delete NAME</code>\n<code>/playlist list</code>")
    action = args[1].lower()
    uid = message.from_user.id
    if action == 'create':
        name = message.text.split(None, 2)[2].strip() if len(message.text.split(None, 2)) >= 3 else ''
        if not name: return await message.reply_text("Use <code>/playlist create My Playlist</code>")
        ok = await create_user_playlist(uid, name)
        return await message.reply_text("✅ Playlist created." if ok else "⚠️ A playlist with that name already exists.")
    if action == 'list':
        pls = await get_user_playlists(uid)
        return await message.reply_text("📂 <b>Your Playlists</b>\n\n" + ("\n".join(f"• <b>{html.escape(p['name'])}</b> — {len(p.get('tracks',[]))} tracks" for p in pls) if pls else "No playlists yet."))
    if action == 'play':
        if len(args) < 3:
            return await message.reply_text("Use <code>/playlist play NAME</code>")
        if message.chat.type not in ("group", "supergroup"):
            return await message.reply_text("❌ Playlist playback must be started in a group voice chat.")
        p = await get_user_playlist(uid, args[2])
        if not p:
            return await message.reply_text("❌ Playlist not found.")
        tracks = p.get('tracks', [])
        if not tracks:
            return await message.reply_text("❌ Playlist is empty.")
        started = 0
        for track in tracks[:100]:
            query = track.get('link') or track.get('vidid') or track.get('title')
            if not query:
                continue
            try:
                details, _ = await YouTube.track(query, videoid=track.get('vidid') or None)
                await stream(
                    _, None, uid, details, message.chat.id,
                    message.from_user.first_name, message.chat.id,
                    video=False, streamtype="youtube", forceplay=False,
                )
                started += 1
            except Exception:
                continue
        if not started:
            return await message.reply_text("❌ None of the playlist tracks could be played.")
        return await message.reply_text(f"▶️ Started <b>{started}</b> track(s) from <b>{html.escape(p['name'])}</b>.")

    if action == 'show':
        if len(args) < 3: return await message.reply_text("Use <code>/playlist show NAME</code>")
        p = await get_user_playlist(uid, args[2])
        if not p: return await message.reply_text("❌ Playlist not found.")
        tracks=p.get('tracks',[])
        text="📂 <b>"+html.escape(p['name'])+"</b>\n\n"+("\n".join(f"{i}. {html.escape(t.get('title','—')[:90])}" for i,t in enumerate(tracks,1)) if tracks else "Playlist is empty.")
        return await message.reply_text(text)
    if action == 'delete':
        if len(args) < 3: return await message.reply_text("Use <code>/playlist delete NAME</code>")
        return await message.reply_text("🗑 Playlist deleted." if await delete_user_playlist(uid,args[2]) else "❌ Playlist not found.")
    if action == 'remove':
        if len(args) < 4 or not args[3].isdigit(): return await message.reply_text("Use <code>/playlist remove NAME NUMBER</code>")
        return await message.reply_text("🗑 Track removed." if await remove_user_playlist_track(uid,args[2],int(args[3])) else "❌ Playlist/track not found.")
    if action == 'add':
        if len(args) < 4: return await message.reply_text("Use <code>/playlist add NAME SONG NAME OR URL</code>")
        p = await get_user_playlist(uid,args[2])
        if not p: return await message.reply_text("❌ Playlist not found. Create it first.")
        query=args[3]
        try:
            details, vidid = await YouTube.track(query)
        except Exception as exc:
            return await message.reply_text("❌ Could not find that song.")
        track={'title':details.get('title','Unknown')[:300], 'link':details.get('link',''), 'vidid':vidid, 'duration':details.get('duration_min','')}
        if len(p.get('tracks',[])) >= 100: return await message.reply_text("❌ Playlist limit is 100 tracks.")
        await add_user_playlist_track(uid,args[2],track)
        return await message.reply_text(f"✅ Added <b>{html.escape(track['title'])}</b> to <b>{html.escape(p['name'])}</b>.")
    return await message.reply_text("❌ Unknown playlist action. Use <code>/playlist</code> for help.")

async def _lyrics_query(query: str):
    """Fetch the fullest available lyrics from LRCLIB.

    Search by the complete query first, then fall back to track_name. Prefer
    plainLyrics because it contains the full unsynchronised text; syncedLyrics
    is only used when plainLyrics is unavailable.
    """
    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"User-Agent": "TrebelxMusic/1.0 (+lyrics)"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        urls = [
            "https://lrclib.net/api/search?q=" + quote_plus(query),
            "https://lrclib.net/api/search?track_name=" + quote_plus(query),
        ]
        data = None
        for url in urls:
            try:
                async with session.get(url) as r:
                    if r.status != 200:
                        continue
                    candidate = await r.json(content_type=None)
                    if isinstance(candidate, list) and candidate:
                        data = candidate
                        break
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                continue
        if not data:
            return None

        def score(item):
            plain = str(item.get("plainLyrics") or "").strip()
            synced = str(item.get("syncedLyrics") or "").strip()
            # Prefer exact-ish matches and complete plain lyrics.
            title = str(item.get("trackName") or "")
            return (
                2 if title.casefold() in query.casefold() or query.casefold() in title.casefold() else 0,
                2 if plain else 1 if synced else 0,
                len(plain) if plain else len(synced),
            )

        best = max(data, key=score)
        lyrics = str(best.get("plainLyrics") or "").strip()
        if not lyrics:
            synced = str(best.get("syncedLyrics") or "")
            lyrics = re.sub(r"\[[^\]]+\]", "", synced).strip()
        if not lyrics:
            return None
        return (
            best.get("trackName") or query,
            best.get("artistName") or "",
            lyrics,
        )

@app.on_message(filters.command("lyrics") & ~BANNED_USERS)
@capture_err
async def lyrics_command(_, message: Message):
    query = message.text.split(None, 1)[1].strip() if len(message.command) > 1 else ""
    if not query and message.reply_to_message:
        reply = message.reply_to_message
        query = reply.text or reply.caption or ""
        if not query and getattr(reply, "audio", None):
            audio = reply.audio
            query = " - ".join(x for x in (getattr(audio, "title", None), getattr(audio, "performer", None)) if x)
        if not query and getattr(reply, "video", None):
            query = getattr(reply.video, "file_name", "") or ""
    if not query:
        return await message.reply_text("🎵 Use <code>/lyrics song name</code> or reply to a song request.")
    status=await message.reply_text("🎤 <b>Searching lyrics…</b>")
    try:
        result=await _lyrics_query(query)
        if not result:
            return await status.edit_text("❌ Lyrics not found for that song.")
        title, artist, lyrics = result
        header = f"🎤 <b>{html.escape(title)}</b>\n👤 {html.escape(artist)}</b>\n\n" if artist else f"🎤 <b>{html.escape(title)}</b>\n\n"

        def _lyrics_chunks(raw: str, first_limit: int = 3500, limit: int = 3800):
            """Split raw lyrics before HTML escaping so entities cannot be broken."""
            result_chunks = []
            current = []
            current_len = 0
            max_len = first_limit - len(header)
            for line in raw.splitlines():
                candidate = line if not current else "\n" + line
                escaped_len = len(html.escape(candidate))
                if current and current_len + escaped_len > max_len:
                    result_chunks.append("".join(current).strip())
                    current, current_len, max_len = [], 0, limit
                    candidate = line
                    escaped_len = len(html.escape(candidate))
                if escaped_len > max_len and not current:
                    # Extremely long lines: split the raw line at safe character
                    # boundaries, then escape each piece independently.
                    start = 0
                    while start < len(line):
                        piece = line[start:start + 3000]
                        result_chunks.append(piece)
                        start += len(piece)
                    current, current_len = [], 0
                    continue
                current.append(candidate)
                current_len += escaped_len
            if current:
                result_chunks.append("".join(current).strip())
            return [x for x in result_chunks if x]

        chunks = _lyrics_chunks(lyrics)
        if not chunks:
            return await status.edit_text("❌ Lyrics were returned empty by the lyrics service.")
        await status.edit_text(header + html.escape(chunks[0]))
        for chunk in chunks[1:]:
            await message.reply_text(html.escape(chunk))
    except Exception as exc:
        await status.edit_text("❌ Lyrics service is temporarily unavailable.")
