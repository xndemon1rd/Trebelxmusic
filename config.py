# Authored By Dev © 2025
import re
from os import getenv
from dotenv import load_dotenv
from pyrogram import filters

# Load environment variables from .env file
load_dotenv()

# ── Core bot config ────────────────────────────────────────────────────────────
def _required_env(name: str) -> str:
    value = getenv(name)
    if not value:
        raise RuntimeError(f"Missing required Railway/Termux variable: {name}")
    return value


API_ID = int(_required_env("API_ID"))
API_HASH = _required_env("API_HASH")
BOT_TOKEN = _required_env("BOT_TOKEN")

OWNER_ID = int(getenv("OWNER_ID", 7044783841))
OWNER_USERNAME = getenv("OWNER_USERNAME", "TrabelxMusic")
BOT_USERNAME = getenv("BOT_USERNAME", "trabelvibebot")
BOT_NAME = getenv("BOT_NAME", "˹𝐓ʀᴇʙᴇʟ ✘ ᴍᴜꜱɪᴄ˼ ♪")
ASSUSERNAME = getenv("ASSUSERNAME", "musicxᴛʀᴇʙᴇʟ")

# ── Database & logging ─────────────────────────────────────────────────────────
MONGO_DB_URI = _required_env("MONGO_DB_URI")
LOGGER_ID = int(getenv("LOGGER_ID", -1002014167331))

# ── Limits (durations in min/sec; sizes in bytes) ──────────────────────────────
DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 300))
SONG_DOWNLOAD_DURATION = int(getenv("SONG_DOWNLOAD_DURATION", "1200"))
SONG_DOWNLOAD_DURATION_LIMIT = int(getenv("SONG_DOWNLOAD_DURATION_LIMIT", "1800"))
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", "157286400"))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", "1288490189"))
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", "30"))
DOWNLOAD_EXTRA_COST_COINS = int(getenv("DOWNLOAD_EXTRA_COST_COINS", "100"))
MAX_DOWNLOAD_BYTES = int(getenv("MAX_DOWNLOAD_BYTES", "1288490189"))
MAX_AUDIO_DOWNLOAD_BYTES = int(getenv("MAX_AUDIO_DOWNLOAD_BYTES", str(TG_AUDIO_FILESIZE_LIMIT)))
DIRECT_DOWNLOAD_TIMEOUT = int(getenv("DIRECT_DOWNLOAD_TIMEOUT", "600"))
API_POLL_TIMEOUT = int(getenv("API_POLL_TIMEOUT", "180"))
DOWNLOAD_RETENTION_HOURS = int(getenv("DOWNLOAD_RETENTION_HOURS", "24"))
CACHE_RETENTION_HOURS = int(getenv("CACHE_RETENTION_HOURS", "48"))
MAX_CACHE_BYTES = int(getenv("MAX_CACHE_BYTES", "536870912"))
STORAGE_CLEANUP_INTERVAL = int(getenv("STORAGE_CLEANUP_INTERVAL", "1800"))
STARTUP_VOICE_CHECK = getenv("STARTUP_VOICE_CHECK", "false").lower() in {"1", "true", "yes", "on"}

# ── AI ─────────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = getenv("GROQ_API_KEY", "")
AI_MODEL = getenv("AI_MODEL", "gpt-5.6-luna")
GEMINI_MODEL = getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = getenv("GROQ_MODEL", "openai/gpt-oss-120b")
AI_IMAGE_MODEL = getenv("AI_IMAGE_MODEL", "gpt-image-2")
AI_MAX_INPUT = int(getenv("AI_MAX_INPUT", "8000"))
AI_ENABLED = bool(OPENAI_API_KEY or GEMINI_API_KEY or GROQ_API_KEY)

# ── External APIs ──────────────────────────────────────────────────────────────
COOKIE_URL = getenv("COOKIE_URL", "").strip()  # optional legacy cookie URL
YTDLP_COOKIES_B64 = getenv("YTDLP_COOKIES_B64", "").strip()  # optional Base64 Netscape cookies.txt
AI_HEALER_ENABLED = getenv("AI_HEALER_ENABLED", "auto").strip().lower()
API_URL = getenv("API_URL")        # optional
VIDEO_API_URL = getenv("VIDEO_API_URL")  # optional
API_KEY = getenv("API_KEY")        # optional
DEEP_API = getenv("DEEP_API")      # optional
# Anime search/stream API used by /cplay. Change this Railway variable if the provider changes.
ANIME_API_BASE_URL = getenv("ANIME_API_BASE_URL", "https://hianime-api-production.up.railway.app/api/v2").rstrip("/")
ANIME_AUDIO_TYPE = getenv("ANIME_AUDIO_TYPE", "sub").strip().lower() or "sub"
ANIME_SERVER = getenv("ANIME_SERVER", "hd-1").strip().lower() or "hd-1"
ANIME_HTTP_TIMEOUT = float(getenv("ANIME_HTTP_TIMEOUT", "20"))

# ── Hosting / deployment ───────────────────────────────────────────────────────
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

# ── Git / updates ──────────────────────────────────────────────────────────────

# ── Support links ──────────────────────────────────────────────────────────────
SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/zxknox")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/zpaveldurov")

# ── Assistant auto-leave ───────────────────────────────────────────────────────
AUTO_LEAVING_ASSISTANT = False
AUTO_LEAVE_ASSISTANT_TIME = int(getenv("ASSISTANT_LEAVE_TIME", "3600"))

# ── Debug ──────────────────────────────────────────────────────────────────────
DEBUG_IGNORE_LOG = True

# ── Spotify (optional) ─────────────────────────────────────────────────────────
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET")

# ── Session strings (optional) ─────────────────────────────────────────────────
STRING1 = getenv("STRING_SESSION")
STRING2 = getenv("STRING_SESSION2")
STRING3 = getenv("STRING_SESSION3")
STRING4 = getenv("STRING_SESSION4")
STRING5 = getenv("STRING_SESSION5")

# ── Media assets ───────────────────────────────────────────────────────────────
START_VIDS = [
    "https://files.catbox.moe/6d0ejr.mp4",
    "https://files.catbox.moe/d941ku.mp4",
    "https://www.image2url.com/r2/default/videos/1789542560216-1e47a2d4-449c-494b-97b4-b9fefb4d4972.mp4",
]
STICKERS = [
    "CAACAgUAAx0Cd6nKUAACASBl_rnalOle6g7qS-ry-aZ1ZpVEnwACgg8AAizLEFfI5wfykoCR4hjp",
    "CAACAgUAAx0Cd6nKUAACATJl_rsEJOsaaPSYGhU7bo7iEwL8AAPMDgACu2PYV8Vb8aT4_HUPHgQ",
]
HELP_IMG_URL = "https://files.catbox.moe/ag0igk.png"
# Media used by the main /start screen and group member welcome.
# Local fallbacks are kept in the handlers so a temporary Catbox outage does not break them.
START_IMG_URL = "https://files.catbox.moe/r71t39.png"
GROUP_WELCOME_IMG_URL = "https://files.catbox.moe/zq3tue.jpg"
PING_VID_URL = "https://files.catbox.moe/3ivvgo.mp4"
PLAYLIST_IMG_URL = "https://files.catbox.moe/hawtk5.jpg"
STATS_VID_URL = "https://telegra.ph/file/e2ab6106ace2e95862372.mp4"
TELEGRAM_AUDIO_URL = "https://files.catbox.moe/hnv4sf.jpg"
TELEGRAM_VIDEO_URL = "https://files.catbox.moe/6d0ejr.mp4"
STREAM_IMG_URL = "https://files.catbox.moe/1d3da7.jpg"
SOUNCLOUD_IMG_URL = "https://files.catbox.moe/zhymxl.jpg"
YOUTUBE_IMG_URL = "https://files.catbox.moe/veykzq.jpg"
SPOTIFY_ARTIST_IMG_URL = SPOTIFY_ALBUM_IMG_URL = SPOTIFY_PLAYLIST_IMG_URL = YOUTUBE_IMG_URL

# ── Helpers ────────────────────────────────────────────────────────────────────
def time_to_seconds(time: str) -> int:
    return sum(int(x) * 60**i for i, x in enumerate(reversed(time.split(":"))))

DURATION_LIMIT = time_to_seconds(f"{DURATION_LIMIT_MIN}:00")

# ───── Bot Introduction Messages ───── #
AYU = ["💞", "🦋", "🔍", "🧪", "⚡️", "🔥", "🎩", "🌈", "🍷", "🥂", "🥃", "🕊️", "🪄", "💌", "🧨"]
AYUV = [
    "ʜᴇʟʟᴏ {0}, 🥀\n\n ɪᴛ'ꜱ ᴍᴇ {1} !\n\n┏━━━━━━━━━━━━━━━━━⧫\n┠┗━━━━━━━━━━━━━━━━━⧫\n┏━━━━━━━━━━━━━━━━━⧫\n┠ ➥ Uᴘᴛɪᴍᴇ : {2}\n┠ ➥ SᴇʀᴠᴇʀSᴛᴏʀᴀɢᴇ : {3}\n┠ ➥ CPU Lᴏᴀᴅ : {4}\n┠ ➥ RAM Cᴏɴsᴜᴘᴛɪᴏɴ : {5}\n┠ ➥ ᴜꜱᴇʀꜱ : {6}\n┠ ➥ ᴄʜᴀᴛꜱ : {7}\n┗━━━━━━━━━━━━━━━━━⧫\n\n🫧 ᴅᴇᴠᴇʟᴏᴩᴇʀ 🪽 ➪ [𝑫𝒆𝒗](https://t.me/xtmonk)",
    "ʜɪɪ, {0} ~\n\n◆ ɪ'ᴍ ᴀ {1} ᴛᴇʟᴇɢʀᴀᴍ ꜱᴛʀᴇᴀᴍɪɴɢ ʙᴏᴛ ᴡɪᴛʜ ꜱᴏᴍᴇ ᴜꜱᴇꜰᴜʟ\n◆ ᴜʟᴛʀᴀ ғᴀsᴛ ᴠᴄ ᴘʟᴀʏᴇʀ ꜰᴇᴀᴛᴜʀᴇꜱ.\n\n✨ ꜰᴇᴀᴛᴜʀᴇꜱ ⚡️\n◆ ʙᴏᴛ ғᴏʀ ᴛᴇʟᴇɢʀᴀᴍ ɢʀᴏᴜᴘs.\n◆ Sᴜᴘᴇʀғᴀsᴛ ʟᴀɢ Fʀᴇᴇ ᴘʟᴀʏᴇʀ.\n◆ ʏᴏᴜ ᴄᴀɴ ᴘʟᴀʏ ᴍᴜꜱɪᴄ + ᴠɪᴅᴇᴏ.\n◆ ʟɪᴠᴇ ꜱᴛʀᴇᴀᴍɪɴɢ.\n◆ ɴᴏ ᴘʀᴏᴍᴏ.\n◆ ʙᴇꜱᴛ ꜱᴏᴜɴᴅ Qᴜᴀʟɪᴛʏ.\n◆ 24×7 ʏᴏᴜ ᴄᴀɴ ᴘʟᴀʏ ᴍᴜꜱɪᴄ.\n◆ ᴀᴅᴅ ᴛʜɪꜱ ʙᴏᴛ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴀɴᴅ ᴍᴀᴋᴇ ɪᴛ ᴀᴅᴍɪɴ ᴀɴᴅ ᴇɴᴊᴏʏ ᴍᴜꜱɪᴄ 🎵.\n\n┏━━━━━━━━━━━━━━━━━⧫\n┠ ◆ ꜱᴜᴘᴘᴏʀᴛɪɴɢ ᴘʟᴀᴛꜰᴏʀᴍꜱ : ʏᴏᴜᴛᴜʙᴇ, ꜱᴘᴏᴛɪꜰʏ,\n┠ ◆ ʀᴇꜱꜱᴏ, ᴀᴘᴘʟᴇᴍᴜꜱɪᴄ , ꜱᴏᴜɴᴅᴄʟᴏᴜᴅ ᴇᴛᴄ.\n┗━━━━━━━━━━━━━━━━━⧫\n┏━━━━━━━━━━━━━━━━━⧫\n┠ ➥ Uᴘᴛɪᴍᴇ : {2}\n┠ ➥ SᴇʀᴠᴇʀSᴛᴏʀᴀɢᴇ : {3}\n┠ ➥ CPU Lᴏᴀᴅ : {4}\n┠ ➥ RAM Cᴏɴsᴜᴘᴛɪᴏɴ : {5}\n┠ ➥ ᴜꜱᴇʀꜱ : {6}\n┠ ➥ ᴄʜᴀᴛꜱ : {7}\n┗━━━━━━━━━━━━━━━━━⧫\n\n🫧 ᴅᴇᴠᴇʟᴏᴩᴇʀ 🪽 ➪ [𝐃ᴇᴠ](https://t.me/jesterxd)",
]

# ── Runtime structures ─────────────────────────────────────────────────────────
BANNED_USERS = filters.user()
adminlist, lyrical, autoclean, confirmer = {}, {}, [], {}

# ── Minimal validation ─────────────────────────────────────────────────────────
if SUPPORT_CHANNEL and not re.match(r"^https?://", SUPPORT_CHANNEL):
    raise SystemExit("[ERROR] - Invalid SUPPORT_CHANNEL URL. Must start with https://")

if SUPPORT_CHAT and not re.match(r"^https?://", SUPPORT_CHAT):
    raise SystemExit("[ERROR] - Invalid SUPPORT_CHAT URL. Must start with https://")
