# Authored By Dev © 2025
from .logging import LOGGER

# Create the main bot object as early as possible so modules importing
# "from TrabelxMusic import app" never see a partially initialized package.
from TrabelxMusic.core.bot import MusicBotClient
app = MusicBotClient()

from TrabelxMusic.core.dir import StorageManager
from TrabelxMusic.misc import dbb, heroku

StorageManager()
dbb()
heroku()

from TrabelxMusic.utils.premium_emoji import install_message_emoji_hooks
install_message_emoji_hooks()


# Load platform APIs only after app/userbot exist.
from .platforms import *
Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
