import discord
from discord.ext import commands
from settings import BOT_STATUS

class YouTubeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        await self.load_extension("bot.commands")
        await self.load_extension("bot.watcher")

        print("[Commands] Loaded commands from Python:")
        for command in self.tree.walk_commands():
            print(f"[Commands] /{command.qualified_name}")

        commands_to_sync = list(self.tree.get_commands())

        print("[Commands] Clearing old commands...")
        self.tree.clear_commands(guild=None)
        await self.tree.sync()

        for command in commands_to_sync:
            self.tree.add_command(command, override=True)

        synced = await self.tree.sync()

        print(f"[Commands] Synced {len(synced)} root commands.")
        for command in self.tree.walk_commands():
            print(f"[Commands] /{command.qualified_name}")

    async def on_ready(self):
        if self.user is None:
            return
        print(f"Logged into Discord as {self.user} ({self.user.id})")
        activity = discord.Activity(type=discord.ActivityType.watching, name=BOT_STATUS)
        await self.change_presence(status=discord.Status.online, activity=activity)

bot = YouTubeBot()