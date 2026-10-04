import asyncio, logging, aiohttp, discord
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from discord.ext import commands, tasks
from bot.storage import (get_state_lock, load_guild_config, load_guild_state, save_guild_state,)
from settings import POLL_INTERVAL_SECONDS
from bot.models import MentionConfig
from bot.notifications import build_mention

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# YouTube feed information
# ---------------------------------------------------------
YOUTUBE_FEED_URL = ("https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")

XML_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}

# ---------------------------------------------------------
# YouTube video model
# ---------------------------------------------------------
@dataclass(slots=True)
class YouTubeVideo:
    video_id: str
    channel_id: str
    channel_name: str
    title: str
    published_at: datetime
    url: str

# ---------------------------------------------------------
# Feed parsing
# ---------------------------------------------------------
def parse_youtube_datetime(value: str) -> datetime:
    """
    Convert YouTube's timestamp into a timezone-aware
    Python datetime.
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

def parse_youtube_feed(xml_text: str) -> list[YouTubeVideo]:
    """
    Convert a YouTube Atom feed into YouTubeVideo objects.
    """
    root = ET.fromstring(xml_text)
    videos: list[YouTubeVideo] = []
    for entry in root.findall("atom:entry", XML_NAMESPACES):
        video_id = entry.findtext("yt:videoId", default="", namespaces=XML_NAMESPACES,)
        channel_id = entry.findtext("yt:channelId",  default="",  namespaces=XML_NAMESPACES,)
        title = entry.findtext("atom:title", default="", namespaces=XML_NAMESPACES,)
        published_text = entry.findtext("atom:published",  default="",  namespaces=XML_NAMESPACES,)
        channel_name = entry.findtext("atom:author/atom:name", default="", namespaces=XML_NAMESPACES,)
        if not (video_id and channel_id and published_text):
            continue
        published_at = parse_youtube_datetime(published_text)
        videos.append(YouTubeVideo(video_id=video_id, channel_id=channel_id, channel_name=(channel_name or channel_id), title=(title or "New YouTube video"), published_at=published_at, url=(f"https://www.youtube.com/watch?v={video_id}")))

    # If several videos appeared between checks,
    # announce them oldest -> newest.
    videos.sort(key=lambda video: video.published_at)
    return videos

async def fetch_youtube_feed(session: aiohttp.ClientSession, channel_id: str) -> list[YouTubeVideo]:
    """
    Fetch the latest YouTube uploads for a channel.
    """
    url = YOUTUBE_FEED_URL.format(channel_id=channel_id)
    async with session.get(url) as response:
        if response.status == 404:
            raise RuntimeError(f"YouTube feed not found for {channel_id}")
        response.raise_for_status()
        xml_text = await response.text()
    return parse_youtube_feed(xml_text)

# ---------------------------------------------------------
# Watcher
# ---------------------------------------------------------
class YouTubeWatcher(commands.Cog):
    """
    Checks YouTube in the background and sends
    new-upload notifications.
    """
    def __init__(self, bot: commands.Bot,):
        self.bot = bot
        # IMPORTANT:
        #
        # Anything published before this exact time
        # will NEVER be announced during this process.
        self.started_at = datetime.now(timezone.utc)
        # Prevent us from hitting a huge number of
        # YouTube feeds simultaneously.
        self.fetch_semaphore = asyncio.Semaphore(8)

    async def cog_load(self):
        """
        Called when this Cog is loaded.
        """
        self.youtube_watcher.start()

    async def cog_unload(self):
        """
        Stop the background loop when the Cog unloads.
        """
        self.youtube_watcher.cancel()

    @tasks.loop(seconds=POLL_INTERVAL_SECONDS)
    async def youtube_watcher(self):
        """
        Main repeating YouTube check.
        """
        try:
            await self.check_for_uploads()
        except Exception:
            # An unexpected failure should be logged,
            # but should NOT kill the watcher forever.
            logger.exception("Unexpected error in YouTube watcher.")

    @youtube_watcher.before_loop
    async def before_youtube_watcher(self):
        """
        Wait until Discord is fully connected before
        beginning checks.
        """
        await self.bot.wait_until_ready()
        print(f"[YouTube] Watcher started at {self.started_at.isoformat()}")

    async def check_for_uploads(self):
        """
        Build a list of everything being watched,
        fetch YouTube feeds, and process new videos.
        """
        # Key:
        # YouTube channel ID
        #
        # Value:
        # list of:
        # (Discord guild ID, Discord channel ID)
        subscriptions: dict[str, list[tuple[int, str, MentionConfig]]] = {}

        # -------------------------------------------------
        # Build subscription map from all Discord servers
        # -------------------------------------------------
        for guild in self.bot.guilds:
            try:
                config = await load_guild_config(guild.id)
            except Exception:
                logger.exception("Could not load config for Discord guild %s", guild.id)
                continue
            if not config.enabled:
                continue
            for (discord_channel_id, announcement_config) in config.announcement_channels.items():
                if not announcement_config.enabled:
                    continue
                # set() also protects against accidental
                # duplicate IDs in the JSON file.
                for youtube_channel_id in set(announcement_config.youtube_channel_ids):
                    subscriptions.setdefault(youtube_channel_id, []).append((guild.id, discord_channel_id, announcement_config.mention))
        if not subscriptions:
            return
        print(f"[YouTube] Checking {len(subscriptions)} unique YouTube channel(s).")

        # -------------------------------------------------
        # Fetch all unique YouTube feeds
        # -------------------------------------------------
        timeout = aiohttp.ClientTimeout(total=20)
        headers = {"User-Agent": ("Mozilla/5.0 (compatible; DiscordYouTubeBot/1.0)")}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            youtube_ids = list(subscriptions.keys())
            fetches = [self.fetch_with_limit(session, channel_id)for channel_id in youtube_ids]
            results = await asyncio.gather(*fetches, return_exceptions=True,)

        # -------------------------------------------------
        # Process feed results
        # -------------------------------------------------
        for (youtube_channel_id, result) in zip(youtube_ids, results):
            if isinstance(result, BaseException):
                logger.warning("Could not check YouTube channel %s: %s", youtube_channel_id, result)
                continue
            destinations = subscriptions[youtube_channel_id]

            for video in result:
                # CRITICAL REQUIREMENT:
                #
                # Never announce anything published
                # before this bot process started.
                if (video.published_at < self.started_at):
                    continue
                for (guild_id, discord_channel_id, mention_config) in destinations:
                    await self.send_video_if_needed(guild_id, discord_channel_id, mention_config, video)

    async def fetch_with_limit(self, session: aiohttp.ClientSession, channel_id: str) -> list[YouTubeVideo]:
        """
        Fetch a feed while limiting concurrent
        requests to YouTube.
        """
        async with self.fetch_semaphore:
            return await fetch_youtube_feed(session, channel_id)

    async def send_video_if_needed(self, guild_id: int, discord_channel_id: str, mention_config: MentionConfig, video: YouTubeVideo):
        """
        Send a notification exactly once to one
        Discord channel.
        """
        async with get_state_lock(guild_id):
            state = await load_guild_state(guild_id)
            sent_video_ids = (state.sent_notifications.setdefault(discord_channel_id, []))
            # Duplicate protection.
            if (video.video_id in sent_video_ids):
                return

            # ---------------------------------------------
            # Find Discord destination
            # ---------------------------------------------
            try:
                channel_id_int = int(discord_channel_id)
            except ValueError:
                logger.error("Invalid Discord channel ID: %s", discord_channel_id)
                return
            channel = self.bot.get_channel(channel_id_int)
            if channel is None:
                try:
                    channel = (await self.bot.fetch_channel(channel_id_int))
                except discord.HTTPException:
                    logger.exception("Could not find Discord channel %s", discord_channel_id)
                    return
            if not isinstance(channel, discord.abc.Messageable):
                logger.warning("Discord channel %s cannot receive messages.", discord_channel_id)
                return

            # ---------------------------------------------
            # Send notification
            # ---------------------------------------------
            mention_text, allowed_mentions = build_mention(mention_config)
            message = (f"{mention_text} **{video.channel_name} uploaded a new video!**\n**{video.title}**\n{video.url}")
            try:
                await channel.send(message, allowed_mentions=allowed_mentions)
            except discord.Forbidden:
                logger.warning("Missing permission to send messages in Discord channel %s", discord_channel_id)
                return
            except discord.HTTPException:
                logger.exception("Discord failed to send a notification to channel %s", discord_channel_id)
                return

            # ---------------------------------------------
            # Record successful notification
            # ---------------------------------------------
            sent_video_ids.append(video.video_id)
            # We do NOT need infinite history.
            #
            # Keep the newest 250 video IDs for each
            # Discord announcement channel.
            if len(sent_video_ids) > 250:
                del sent_video_ids[:-250]
            await save_guild_state(state)
            print(f"[YouTube] Sent {video.video_id} to Discord channel {discord_channel_id}")

async def setup(bot: commands.Bot):
    await bot.add_cog(YouTubeWatcher(bot))