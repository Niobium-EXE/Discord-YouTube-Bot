import discord
from discord import app_commands
from discord.ext import commands

from bot.models import (
    AnnouncementChannelConfig,
)
from bot.storage import (
    get_guild_lock,
    load_guild_config,
    load_youtube_cache,
    save_guild_config,
    save_youtube_channel_info,
)
from bot.youtube import (
    YouTubeLookupError,
    resolve_youtube_channel,
)


async def require_server_owner(
    interaction: discord.Interaction,
) -> bool:
    """
    Make sure the command is being used inside
    a Discord server and by that server's owner.
    """

    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message(
            "This command can only be used "
            "inside a Discord server.",
            ephemeral=True,
        )

        return False

    if interaction.user.id != guild.owner_id:
        await interaction.response.send_message(
            "Only the server owner can change "
            "YouTube notification settings.",
            ephemeral=True,
        )

        return False

    return True


class GeneralCommands(commands.Cog):
    """
    Commands not belonging to a command group.
    """

    def __init__(
        self,
        bot: commands.Bot,
    ):
        self.bot = bot

    @app_commands.command(
        name="ping",
        description=(
            "Check whether the bot is online."
        ),
    )
    async def ping(
        self,
        interaction: discord.Interaction,
    ):
        await interaction.response.send_message(
            "The bot is online.",
            ephemeral=True,
        )


class YouTubeCommands(
    commands.GroupCog,
    group_name="youtube",
    group_description=(
        "Manage YouTube notifications."
    ),
):
    """
    Creates:

        /youtube add
        /youtube remove
        /youtube list
    """

    def __init__(
        self,
        bot: commands.Bot,
    ):
        self.bot = bot


    @app_commands.command(
        name="add",
        description=(
            "Add a YouTube channel to this "
            "Discord channel."
        ),
    )
    @app_commands.describe(
        channel=(
            "YouTube @handle, channel URL, "
            "or UC channel ID"
        )
    )
    async def add(
        self,
        interaction: discord.Interaction,
        channel: str,
    ):
        if not await require_server_owner(
            interaction
        ):
            return

        guild = interaction.guild

        if guild is None:
            return

        discord_channel_id = str(
            interaction.channel_id
        )

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        try:
            youtube_channel = (
                await resolve_youtube_channel(
                    channel
                )
            )

        except YouTubeLookupError as error:
            await interaction.followup.send(
                str(error),
                ephemeral=True,
            )

            return

        # Save friendly information separately.
        await save_youtube_channel_info(
            youtube_channel
        )

        # Lock this server while changing config.
        async with get_guild_lock(
            guild.id
        ):
            config = await load_guild_config(
                guild.id
            )

            # If this Discord channel has never
            # been configured before, adding the
            # first YouTuber automatically makes
            # it an announcement channel.
            if (
                discord_channel_id
                not in
                config.announcement_channels
            ):
                config.announcement_channels[
                    discord_channel_id
                ] = AnnouncementChannelConfig()

            announcement_config = (
                config.announcement_channels[
                    discord_channel_id
                ]
            )

            channel_id = (
                youtube_channel.channel_id
            )

            if (
                channel_id
                in announcement_config
                .youtube_channel_ids
            ):
                await interaction.followup.send(
                    (
                        f"**{youtube_channel.display_name}** "
                        "is already being watched in "
                        "this Discord channel."
                    ),
                    ephemeral=True,
                )

                return

            announcement_config.youtube_channel_ids.append(
                channel_id
            )

            await save_guild_config(
                config
            )

        handle_text = (
            f" ({youtube_channel.handle})"
            if youtube_channel.handle
            else ""
        )

        await interaction.followup.send(
            (
                "Added "
                f"**{youtube_channel.display_name}**"
                f"{handle_text}.\n\n"
                "Stored YouTube ID:\n"
                f"`{youtube_channel.channel_id}`"
            ),
            ephemeral=True,
        )


    @app_commands.command(
        name="remove",
        description=(
            "Remove a YouTube channel from "
            "this Discord channel."
        ),
    )
    @app_commands.describe(
        channel=(
            "YouTube @handle, channel URL, "
            "or UC channel ID"
        )
    )
    async def remove(
        self,
        interaction: discord.Interaction,
        channel: str,
    ):
        if not await require_server_owner(
            interaction
        ):
            return

        guild = interaction.guild

        if guild is None:
            return

        discord_channel_id = str(
            interaction.channel_id
        )

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        try:
            youtube_channel = (
                await resolve_youtube_channel(
                    channel
                )
            )

        except YouTubeLookupError as error:
            await interaction.followup.send(
                str(error),
                ephemeral=True,
            )

            return

        async with get_guild_lock(
            guild.id
        ):
            config = await load_guild_config(
                guild.id
            )

            announcement_config = (
                config.announcement_channels.get(
                    discord_channel_id
                )
            )

            if announcement_config is None:
                await interaction.followup.send(
                    (
                        "This Discord channel is not "
                        "configured as a YouTube "
                        "announcement channel."
                    ),
                    ephemeral=True,
                )

                return

            channel_id = (
                youtube_channel.channel_id
            )

            if (
                channel_id
                not in announcement_config
                .youtube_channel_ids
            ):
                await interaction.followup.send(
                    (
                        f"**{youtube_channel.display_name}** "
                        "is not being watched in this "
                        "Discord channel."
                    ),
                    ephemeral=True,
                )

                return

            announcement_config.youtube_channel_ids.remove(
                channel_id
            )

            await save_guild_config(
                config
            )

        await interaction.followup.send(
            (
                "Removed "
                f"**{youtube_channel.display_name}** "
                "from this Discord channel."
            ),
            ephemeral=True,
        )


    @app_commands.command(
        name="list",
        description=(
            "List YouTube channels watched in "
            "this Discord channel."
        ),
    )
    async def list_channels(
        self,
        interaction: discord.Interaction,
    ):
        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "This command can only be used "
                "inside a Discord server.",
                ephemeral=True,
            )

            return

        discord_channel_id = str(
            interaction.channel_id
        )

        config = await load_guild_config(
            guild.id
        )

        announcement_config = (
            config.announcement_channels.get(
                discord_channel_id
            )
        )

        if announcement_config is None:
            await interaction.response.send_message(
                (
                    "This Discord channel is not "
                    "configured for YouTube "
                    "notifications."
                ),
                ephemeral=True,
            )

            return

        youtube_ids = (
            announcement_config
            .youtube_channel_ids
        )

        if not youtube_ids:
            await interaction.response.send_message(
                (
                    "No YouTube channels are being "
                    "watched here."
                ),
                ephemeral=True,
            )

            return

        cache = await load_youtube_cache()

        lines = []

        for channel_id in youtube_ids:

            info = cache.channels.get(
                channel_id
            )

            if info is None:
                lines.append(
                    f"• `{channel_id}`"
                )

                continue

            handle_text = (
                f" — {info.handle}"
                if info.handle
                else ""
            )

            lines.append(
                (
                    f"• **{info.display_name}**"
                    f"{handle_text}"
                )
            )

        # Keep the Discord response manageable.
        if len(lines) > 25:
            hidden_count = (
                len(lines) - 25
            )

            lines = lines[:25]

            lines.append(
                (
                    f"\n...and {hidden_count} "
                    "more."
                )
            )

        message = (
            "**YouTube channels watched here:**\n\n"
            + "\n".join(lines)
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )


async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        GeneralCommands(bot)
    )

    await bot.add_cog(
        YouTubeCommands(bot)
    )