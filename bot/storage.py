import asyncio, boto3
from pathlib import Path
from botocore.client import Config
from botocore.exceptions import ClientError
from bot.models import GuildConfig, GuildState, YouTubeChannelCache, YouTubeChannelInfo
from settings import LOCAL_DATA_DIR, S3_ACCESS_KEY, S3_BUCKET, S3_ENDPOINT, S3_REGION, S3_SECRET_KEY, S3_URL_STYLE, bucket_is_configured

# ---------------------------------------------------------
# Local storage paths
# ---------------------------------------------------------

DATA_DIRECTORY = Path(LOCAL_DATA_DIR)
GUILD_DIRECTORY = DATA_DIRECTORY / "guilds"
STATE_DIRECTORY = DATA_DIRECTORY / "state"
YOUTUBE_DIRECTORY = DATA_DIRECTORY / "youtube"
YOUTUBE_CACHE_FILE = YOUTUBE_DIRECTORY / "channels.json"

# ---------------------------------------------------------
# Locks
# ---------------------------------------------------------

# Each Discord server gets its own lock.
#
# This prevents two commands from editing the same
# server configuration at exactly the same time.

_guild_locks: dict[str, asyncio.Lock] = {}
_state_locks: dict[str, asyncio.Lock] = {}
_youtube_cache_lock = asyncio.Lock()

def get_guild_lock(guild_id: int | str) -> asyncio.Lock:
    """
    Return the lock belonging to a Discord server.
    """
    guild_id = str(guild_id)
    if guild_id not in _guild_locks:
        _guild_locks[guild_id] = asyncio.Lock()
    return _guild_locks[guild_id]

def get_state_lock(guild_id: int | str) -> asyncio.Lock:
    """
    Return the runtime-state lock for a Discord server.

    This prevents two notification jobs from editing
    the same state file at the same time.
    """
    guild_id = str(guild_id)
    if guild_id not in _state_locks:
        _state_locks[guild_id] = asyncio.Lock()
    return _state_locks[guild_id]

# ---------------------------------------------------------
# S3
# ---------------------------------------------------------
_s3_client = None

def get_s3_client():
    """
    Create the S3 client once, then reuse it.
    """
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    if not bucket_is_configured():
        raise RuntimeError("S3 storage was requested, but bucket credentials are not configured.")
    _s3_client = boto3.client("s3", endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY, region_name=S3_REGION, config=Config(s3={"addressing_style": S3_URL_STYLE}))
    return _s3_client

# ---------------------------------------------------------
# Common helpers
# ---------------------------------------------------------

def get_guild_storage_key(guild_id: int | str) -> str:
    return f"guilds/{guild_id}.json"

def get_guild_state_storage_key(guild_id: int | str) -> str:
    """
    Return the bucket/local-storage key for
    notification runtime state.
    """
    return f"state/{guild_id}.json"

def create_default_guild_config(guild_id: int | str) -> GuildConfig:
    return GuildConfig(guild_id=str(guild_id))

def create_default_guild_state(guild_id: int | str) -> GuildState:
    return GuildState(guild_id=str(guild_id))

def create_default_youtube_cache() -> YouTubeChannelCache:
    return YouTubeChannelCache()

# ---------------------------------------------------------
# Local guild storage
# ---------------------------------------------------------
def _load_guild_local(guild_id: int | str) -> GuildConfig:
    GUILD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    file_path = (GUILD_DIRECTORY / f"{guild_id}.json")
    if not file_path.exists():
        return create_default_guild_config(guild_id)
    contents = file_path.read_text(encoding="utf-8")
    return GuildConfig.model_validate_json(contents)

def _load_guild_state_local(guild_id: int | str) -> GuildState:
    """
    Load notification state from local storage.
    """
    STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    file_path = (STATE_DIRECTORY / f"{guild_id}.json")
    if not file_path.exists():
        return create_default_guild_state(guild_id)
    contents = file_path.read_text(encoding="utf-8")
    return GuildState.model_validate_json(contents)

def _save_guild_local(config: GuildConfig) -> None:
    GUILD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    file_path = (GUILD_DIRECTORY / f"{config.guild_id}.json")
    json_data = config.model_dump_json(indent=2)
    file_path.write_text(json_data, encoding="utf-8")

def _save_guild_state_local(state: GuildState) -> None:
    """
    Save notification state locally.
    """
    STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    file_path = (STATE_DIRECTORY / f"{state.guild_id}.json")
    json_data = state.model_dump_json(indent=2)
    file_path.write_text(json_data, encoding="utf-8")

# ---------------------------------------------------------
# Local YouTube cache
# ---------------------------------------------------------
def _load_youtube_cache_local() -> YouTubeChannelCache:
    YOUTUBE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    if not YOUTUBE_CACHE_FILE.exists():
        return create_default_youtube_cache()
    contents = YOUTUBE_CACHE_FILE.read_text(encoding="utf-8")
    return YouTubeChannelCache.model_validate_json(contents)

def _save_youtube_cache_local(cache: YouTubeChannelCache) -> None:
    YOUTUBE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    json_data = cache.model_dump_json(indent=2)
    YOUTUBE_CACHE_FILE.write_text(json_data, encoding="utf-8")

# ---------------------------------------------------------
# S3 guild storage
# ---------------------------------------------------------
def _load_guild_s3(guild_id: int | str) -> GuildConfig:
    client = get_s3_client()
    key = get_guild_storage_key(guild_id)
    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=key)
    except ClientError as error:
        error_code = str(error.response.get("Error", {}).get("Code", ""))
        if error_code in {"NoSuchKey", "404", "NotFound"}:
            return create_default_guild_config(guild_id)
        raise
    contents = (response["Body"].read().decode("utf-8"))
    return GuildConfig.model_validate_json(contents)

def _load_guild_state_s3(guild_id: int | str) -> GuildState:
    """
    Load notification state from the Railway bucket.
    """
    client = get_s3_client()
    key = get_guild_state_storage_key(guild_id)
    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=key)
    except ClientError as error:
        error_code = str(error.response.get("Error", {}).get("Code", ""))
        if error_code in {"NoSuchKey", "404", "NotFound"}:
            return create_default_guild_state(guild_id)
        raise
    contents = (response["Body"].read().decode("utf-8"))
    return GuildState.model_validate_json(contents)

def _save_guild_s3(config: GuildConfig,) -> None:
    client = get_s3_client()
    key = get_guild_storage_key(config.guild_id)
    json_data = config.model_dump_json(indent=2)
    client.put_object(Bucket=S3_BUCKET, Key=key, Body=json_data.encode("utf-8"), ContentType="application/json")

def _save_guild_state_s3(state: GuildState) -> None:
    """
    Save notification state to the Railway bucket.
    """
    client = get_s3_client()
    key = get_guild_state_storage_key(state.guild_id)
    json_data = state.model_dump_json(indent=2)
    client.put_object(Bucket=S3_BUCKET, Key=key, Body=json_data.encode("utf-8"), ContentType="application/json")

# ---------------------------------------------------------
# S3 YouTube cache
# ---------------------------------------------------------
YOUTUBE_CACHE_KEY = "youtube/channels.json"

def _load_youtube_cache_s3() -> YouTubeChannelCache:
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=YOUTUBE_CACHE_KEY)
    except ClientError as error:
        error_code = str(error.response .get("Error", {}) .get("Code", ""))
        if error_code in {"NoSuchKey", "404", "NotFound"}:
            return create_default_youtube_cache()
        raise
    contents = (response["Body"].read().decode("utf-8"))
    return YouTubeChannelCache.model_validate_json(contents)

def _save_youtube_cache_s3(cache: YouTubeChannelCache) -> None:
    client = get_s3_client()
    json_data = cache.model_dump_json(indent=2)

    client.put_object(Bucket=S3_BUCKET, Key=YOUTUBE_CACHE_KEY, Body=json_data.encode("utf-8"), ContentType="application/json")

# ---------------------------------------------------------
# Public guild functions
# ---------------------------------------------------------
async def load_guild_config(guild_id: int | str) -> GuildConfig:
    if bucket_is_configured():
        return await asyncio.to_thread(_load_guild_s3, guild_id)

    return await asyncio.to_thread(_load_guild_local, guild_id)

async def save_guild_config(config: GuildConfig) -> None:
    if bucket_is_configured():
        await asyncio.to_thread(_save_guild_s3, config)
        return
    await asyncio.to_thread(_save_guild_local, config)

# ---------------------------------------------------------
# Public YouTube cache functions
# ---------------------------------------------------------
async def load_youtube_cache() -> YouTubeChannelCache:
    if bucket_is_configured():
        return await asyncio.to_thread(_load_youtube_cache_s3)
    return await asyncio.to_thread(_load_youtube_cache_local)

async def save_youtube_cache(cache: YouTubeChannelCache) -> None:
    if bucket_is_configured():
        await asyncio.to_thread(_save_youtube_cache_s3, cache)
        return
    await asyncio.to_thread(_save_youtube_cache_local, cache)

async def save_youtube_channel_info(info: YouTubeChannelInfo) -> None:
    """
    Add or update a YouTube channel in the
    friendly-name cache.
    """
    async with _youtube_cache_lock:
        cache = await load_youtube_cache()
        cache.channels[info.channel_id] = info
        await save_youtube_cache(cache)

async def load_guild_state(guild_id: int | str) -> GuildState:
    """
    Load runtime state for one Discord server.
    """
    if bucket_is_configured():
        return await asyncio.to_thread(_load_guild_state_s3, guild_id)
    return await asyncio.to_thread(_load_guild_state_local, guild_id)

async def save_guild_state(state: GuildState) -> None:
    """
    Save runtime state for one Discord server.
    """
    if bucket_is_configured():
        await asyncio.to_thread(_save_guild_state_s3, state)
        return
    await asyncio.to_thread(_save_guild_state_local, state)