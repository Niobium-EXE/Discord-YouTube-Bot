import discord

from bot.models import MentionConfig


def build_mention(
    config: MentionConfig,
) -> tuple[str, discord.AllowedMentions]:
    """
    Build the mention text and Discord AllowedMentions
    object for an announcement.

    We explicitly restrict which mentions Discord
    is allowed to process.

    This is important because YouTube video titles
    and channel names are outside our control.
    """

    if config.type == "everyone":
        return (
            "@everyone\n",
            discord.AllowedMentions(
                everyone=True,
                users=False,
                roles=False,
                replied_user=False,
            ),
        )

    if (
        config.type == "role"
        and config.role_id
    ):
        try:
            role_id = int(
                config.role_id
            )

        except ValueError:
            return (
                "",
                discord.AllowedMentions.none(),
            )

        return (
            f"<@&{role_id}>\n",
            discord.AllowedMentions(
                everyone=False,
                users=False,

                # ONLY this particular role is
                # allowed to be pinged.
                roles=[
                    discord.Object(
                        id=role_id
                    )
                ],

                replied_user=False,
            ),
        )

    return (
        "",
        discord.AllowedMentions.none(),
    )