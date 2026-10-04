from typing import Literal

from pydantic import BaseModel, Field


class MentionConfig(BaseModel):
    """
    Controls what gets pinged when a notification is sent.
    """

    type: Literal["none", "everyone", "role"] = "none"

    role_id: str | None = None


class AnnouncementChannelConfig(BaseModel):
    """
    Configuration for one Discord announcement channel.
    """

    enabled: bool = True

    # IMPORTANT:
    # We store permanent YouTube channel IDs here,
    # not @handles.
    youtube_channel_ids: list[str] = Field(
        default_factory=list
    )

    mention: MentionConfig = Field(
        default_factory=MentionConfig
    )


class GuildConfig(BaseModel):
    """
    Complete configuration for one Discord server.
    """

    guild_id: str

    enabled: bool = True

    announcement_channels: dict[
        str,
        AnnouncementChannelConfig
    ] = Field(
        default_factory=dict
    )


class YouTubeChannelInfo(BaseModel):
    """
    Friendly information about a YouTube channel.

    This is NOT used as the permanent subscription ID.
    The permanent ID is channel_id.
    """

    channel_id: str

    display_name: str

    handle: str | None = None

    channel_url: str


class YouTubeChannelCache(BaseModel):
    """
    Cached display information for YouTube channels.

    Key:
        YouTube UC... channel ID

    Value:
        Friendly metadata for displaying the channel
        on Discord and on the website.
    """

    channels: dict[
        str,
        YouTubeChannelInfo
    ] = Field(
        default_factory=dict
    )

class GuildState(BaseModel):
    """
    Runtime state for one Discord server.

    This is separate from the guild's configuration.
    """

    guild_id: str

    # Key:
    # Discord announcement channel ID
    #
    # Value:
    # Recently sent YouTube video IDs
    sent_notifications: dict[
        str,
        list[str]
    ] = Field(
        default_factory=dict
    )