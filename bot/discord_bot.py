import discord
from discord.ext import commands
from settings import BOT_STATUS

class YouTubeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        # -------------------------------------------------
        # Load all of our bot modules first.
        # -------------------------------------------------
        await self.load_extension("bot.commands")
        await self.load_extension("bot.watcher")
        # -------------------------------------------------
        # FORCE REFRESH GLOBAL SLASH COMMANDS
        # -------------------------------------------------
        print("[Commands] Loaded commands from Python:")
        for command in self.tree.walk_commands():
            print(f"[Commands] /{command.qualified_name}")
        # Save the CURRENT commands before clearing them. These are the commands that were just loaded from bot.commands.
        current_commands = list(self.tree.get_commands())
        print("[Commands] Clearing old global commands from discord...")
        # Remove everything from the local global tree.
        self.tree.clear_commands(guild=None)
        # Sync the now-empty tree. This tells Discord: "This application currently has zero global commands."
        await self.tree.sync()
        print("[Commands] Old global commands cleared.")
        # -------------------------------------------------
        # Put our current commands back into the tree.
        # -------------------------------------------------
        print("[Commands] Restoring current commands...")
        for command in current_commands:
            self.tree.add_command(command, override=True)
        # -------------------------------------------------
        # Sync the CURRENT command list to Discord.
        # -------------------------------------------------
        synced_commands = await self.tree.sync()
        print("[Commands] Current global commands synced.")
        print(f"[Commands] Discord now has {len(synced_commands)} root command(s).")
        print("[Commands Final command tree:")
        for command in self.tree.walk_commands():
            print(f"[Commands] /{command.qualified_name}")
            print("[Commands] Slash command refresh complete.")

    async def on_ready(self):
        if self.user is None:
            return
        print(f"Logged into Discord as {self.user} ({self.user.id})")
        activity = discord.Activity(type=discord.ActivityType.watching, name=BOT_STATUS)
        await self.change_presence(status=discord.Status.online, activity=activity)

bot = YouTubeBot()