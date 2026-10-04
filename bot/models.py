from typing import Literal
from pydantic import BaseModel, Field

class MentionConfig(BaseModel):
    """
    Controls what gets pinged when a notification is sent.

    type can be:
        none
        everyone
        role
    """
    type: Literal["none", "everyone", "role"] = "none"
    role_id: str | None = None

class AnnouncementChannelConfig(BaseModel):
    """
    Configuration for one Discord announcement channel.
    """
    enabled: bool = True
    # YouTube CHANNEL IDs go here.
    #
    # Example:
    # UCXuqSBlHAE6Xw-yeJA0Tunw
    #
    # We intentionally do NOT store @handles here.
    youtube_channel_ids: list[str] = Field(default_factory=list)
    mention: MentionConfig = Field(default_factory=MentionConfig)

class GuildConfig(BaseModel):
    """
    Complete configuration for one Discord server.
    """
    guild_id: str
    enabled: bool = True
    # Key:
    # Discord channel ID
    #
    # Value:
    # Configuration for that announcement channel
    announcement_channels: dict[str, AnnouncementChannelConfig] = Field(default_factory=dict)