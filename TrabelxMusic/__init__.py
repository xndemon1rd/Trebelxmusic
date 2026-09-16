# Authored By Certified Coders © 2025
from TrabelxMusic.core.bot import MusicBotClient
from TrabelxMusic.core.dir import StorageManager
from TrabelxMusic.core.userbot import Userbot
from TrabelxMusic.misc import dbb, heroku

from .logging import LOGGER

StorageManager()
dbb()
heroku()

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
