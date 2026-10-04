import asyncio
from bot.discord_bot import bot
from settings import DISCORD_TOKEN

async def main():
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())