import asyncio
from pathlib import Path
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from bot.models import GuildConfig
from settings import LOCAL_DATA_DIR, S3_ACCESS_KEY, S3_BUCKET, S3_ENDPOINT, S3_REGION, S3_SECRET_KEY, S3_URL_STYLE, bucket_is_configured

# ---------------------------------------------------------
# Local storage paths
# ---------------------------------------------------------
DATA_DIRECTORY = Path(LOCAL_DATA_DIR)
GUILD_DIRECTORY = DATA_DIRECTORY / "guilds"

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
    # noinspection PyTypeChecker
    _s3_client = boto3.client("s3", endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY, region_name=S3_REGION, config=Config(s3={"addressing_style": S3_URL_STYLE}))
    return _s3_client

# ---------------------------------------------------------
# Common helpers
# ---------------------------------------------------------
def get_guild_storage_key(guild_id: int | str) -> str:
    """
    Returns the path/key for a server's configuration.

    Example:

        guilds/123456789.json
    """
    return f"guilds/{guild_id}.json"

def create_default_guild_config(guild_id: int | str) -> GuildConfig:
    """
    Create a brand-new empty server configuration.
    """
    return GuildConfig(guild_id=str(guild_id))

# ---------------------------------------------------------
# LOCAL FILE STORAGE
# ---------------------------------------------------------
def _load_guild_local(guild_id: int | str) -> GuildConfig:
    """
    Load a guild config from the local data folder.
    """
    GUILD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    file_path = (GUILD_DIRECTORY / f"{guild_id}.json")
    if not file_path.exists():
        return create_default_guild_config(guild_id)
    contents = file_path.read_text(encoding="utf-8")
    return GuildConfig.model_validate_json(contents)

def _save_guild_local(config: GuildConfig) -> None:
    """
    Save a guild configuration locally.
    """
    GUILD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    file_path = (GUILD_DIRECTORY / f"{config.guild_id}.json")
    json_data = config.model_dump_json(indent=2)
    file_path.write_text(json_data, encoding="utf-8")

# ---------------------------------------------------------
# S3 / RAILWAY BUCKET STORAGE
# ---------------------------------------------------------
def _load_guild_s3(guild_id: int | str) -> GuildConfig:
    """
    Load a guild configuration from the Railway bucket.
    """
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

def _save_guild_s3(config: GuildConfig) -> None:
    """
    Save a guild configuration to the Railway bucket.
    """
    client = get_s3_client()
    key = get_guild_storage_key(config.guild_id)
    json_data = config.model_dump_json(indent=2)
    client.put_object( Bucket=S3_BUCKET, Key=key, Body=json_data.encode("utf-8"), ContentType="application/json")

# ---------------------------------------------------------
# PUBLIC FUNCTIONS
# ---------------------------------------------------------
async def load_guild_config(guild_id: int | str) -> GuildConfig:
    """
    Load a guild configuration.

    Railway:
        Reads from S3.

    Local development:
        Reads from ./data/guilds/
    """
    if bucket_is_configured():
        return await asyncio.to_thread(_load_guild_s3, guild_id)
    return await asyncio.to_thread(_load_guild_local, guild_id)

async def save_guild_config(config: GuildConfig) -> None:
    """
    Save a guild configuration.

    Railway:
        Saves to S3.

    Local development:
        Saves to ./data/guilds/
    """
    if bucket_is_configured():
        await asyncio.to_thread(_save_guild_s3, config)
        return
    await asyncio.to_thread(_save_guild_local, config)