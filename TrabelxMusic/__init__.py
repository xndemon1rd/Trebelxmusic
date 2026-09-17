# Authored By Dev © 2025
from TrabelxMusic.core.bot import MusicBotClient
from TrabelxMusic.core.dir import StorageManager
from TrabelxMusic.core.userbot import Userbot
from TrabelxMusic.misc import dbb, heroku

from .logging import LOGGER
from TrabelxMusic.utils.premium_emoji import install_message_emoji_hooks

StorageManager()
dbb()
heroku()

install_message_emoji_hooks()
app = MusicBotClient()
userbot = Userbot()


from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
