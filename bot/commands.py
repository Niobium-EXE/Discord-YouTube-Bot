import discord
from discord import app_commands
from discord.ext import commands

class YouTubeCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check whether the YouTube notification bot is online.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("The bot is online.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(YouTubeCommands(bot))