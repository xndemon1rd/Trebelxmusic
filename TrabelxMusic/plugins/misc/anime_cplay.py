# Authored By Dev © 2026
"""Anime voice-chat playback for /cplay."""
from urllib.parse import quote
import httpx
from pyrogram import filters
from pyrogram.types import Message
import config
from TrabelxMusic import app
from TrabelxMusic.core.call import StreamController
from TrabelxMusic.utils.stream.queue import put_queue
from TrabelxMusic.utils.errors import capture_err

def _clean(value): return "" if value is None else str(value).strip()

def _first(mapping, *keys):
    if not isinstance(mapping, dict): return None
    for key in keys:
        value=mapping.get(key)
        if value not in (None,"",[],{}): return value
    return None

def _unwrap(data): return data.get("data",data) if isinstance(data,dict) else data

async def _api_get(path, params=None):
    url=f"{config.ANIME_API_BASE_URL}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=config.ANIME_HTTP_TIMEOUT,follow_redirects=True) as client:
        response=await client.get(url,params=params); response.raise_for_status(); return response.json()

async def search_anime(query):
    data=_unwrap(await _api_get("search",{"keyword":query,"page":1})); results=_first(data,"animes","response","results") or []
    return results if isinstance(results,list) else []

async def get_episodes(anime_id):
    data=_unwrap(await _api_get(f"episodes/{quote(anime_id,safe='')}")); episodes=_first(data,"episodes") or []
    return episodes if isinstance(episodes,list) else []

async def get_stream(episode_id):
    attempts=[(config.ANIME_SERVER,config.ANIME_AUDIO_TYPE),("hd-1","sub"),("hd-2","sub")]; seen=set()
    for server,audio_type in attempts:
        if (server,audio_type) in seen: continue
        seen.add((server,audio_type))
        try: data=_unwrap(await _api_get("stream",{"id":episode_id,"server":server,"type":audio_type}))
        except Exception: continue
        sources=_first(data,"sources","videos","sourcesList") or []
        if isinstance(sources,dict): sources=list(sources.values())
        if not isinstance(sources,list): continue
        for source in sources:
            if not isinstance(source,dict): continue
            url=_first(source,"url","file","link","source")
            if url and str(url).startswith(("http://","https://")):
                return str(url),_clean(_first(source,"referer","referrer"))
    return None,None

def _episode_number(ep):
    try: return int(_first(ep,"episodeNumber","episode","number","ep"))
    except (TypeError,ValueError): return None

@app.on_message(filters.command("cplay") & filters.group)
@capture_err
async def anime_cplay(_,message:Message):
    if len(message.command)<2: return await message.reply_text("🎌 Usage: `/cplay <anime name>`\nExample: `/cplay Naruto`\n\nEpisode: `/cplay Naruto ep 5`")
    args=message.command[1:]; wanted=1
    if len(args)>=2 and args[-2].lower()=="ep" and args[-1].isdigit(): wanted=max(1,int(args[-1])); args=args[:-2]
    anime_name=" ".join(args).strip()
    if not anime_name: return await message.reply_text("🎌 Please provide an anime name.")
    status=await message.reply_text("🎌 Searching anime…")
    try:
        results=await search_anime(anime_name)
        if not results: return await status.edit_text("❌ Anime not found.")
        anime=results[0]; anime_id=_clean(_first(anime,"id","animeId","slug")); title=_clean(_first(anime,"title","name","alternativeTitle")) or anime_name
        if not anime_id: return await status.edit_text("❌ Anime source returned no usable ID.")
        episodes=await get_episodes(anime_id); episode=next((e for e in episodes if _episode_number(e)==wanted),None) or (episodes[0] if episodes else None)
        if not episode: return await status.edit_text(f"❌ No episodes found for **{title}**.")
        episode_id=_clean(_first(episode,"id","episodeId","episode_id")); ep_no=_episode_number(episode) or wanted
        if not episode_id: return await status.edit_text("❌ Anime source returned no playable episode ID.")
        stream_url,referer=await get_stream(episode_id)
        if not stream_url: return await status.edit_text("❌ No playable anime stream was returned.")
        chat_id=message.chat.id; user_name=message.from_user.first_name if message.from_user else "User"; user_id=message.from_user.id if message.from_user else 0
        await StreamController.force_stop_stream(chat_id)
        ffmpeg_params=None
        if referer:
            safe_ref=referer.replace('"',''); ffmpeg_params=f'-headers "Referer: {safe_ref}\\r\\nUser-Agent: Mozilla/5.0\\r\\n"'
        await StreamController.join_call(chat_id,chat_id,stream_url,video=False,image=_first(anime,"poster","thumbnail","image"),ffmpeg_params=ffmpeg_params)
        duration=_clean(_first(episode,"duration","durationText")) or "0:00"; queue_id=f"anime_{anime_id}_ep_{ep_no}"
        await put_queue(chat_id,chat_id,stream_url,f"{title} — Episode {ep_no}",duration,user_name,queue_id,user_id,"anime",forceplay=True)
        await status.edit_text(f"🎌 **{title}**\n🎬 Episode: **{ep_no}**\n▶️ Now playing in the voice chat.")
    except httpx.HTTPError as exc: await status.edit_text(f"❌ Anime source is unavailable right now.\n`{str(exc)[:300]}`")
    except Exception as exc: await status.edit_text(f"❌ Anime playback failed.\n`{str(exc)[:300]}`")
