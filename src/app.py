import discord
from discord.ext import commands
from osu_api import OsuApiV2
from db.db import Database
import aiohttp
from loguru import logger

from config import DISCORD_TOKEN, SERVER_ID


class OsuBot(commands.Bot):
    osuapi: OsuApiV2
    db: Database
    lvguild: discord.Guild
    session: aiohttp.ClientSession

    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = True

        self.osuapi = OsuApiV2()
        self.db = Database()

        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.osuapi.session = self.session
        await self.osuapi.refresh_token()
        await self.db.setup_hook()

    async def on_ready(self):
        guildstring = ""
        for guild in self.guilds:
            guildstring += f"{guild.name}, "

        logger.info(
            f"""Logged in as {self.user} (ID: {self.user.id if self.user else "unknown"}) Servers: {guildstring.removesuffix(", ")}"""
        )

        guild = self.get_guild(SERVER_ID)
        if guild is None:
            logger.error(f"Could not find guild with ID {SERVER_ID}")
            raise RuntimeError(f"Could not find guild with ID {SERVER_ID}")
        self.lvguild = guild

        await self.load_extension("cogs.events")
        await self.load_extension("cogs.commands")
        await self.load_extension("cogs.link_user")
        await self.load_extension("cogs.roles")
        await self.load_extension("cogs.user_newbest")

    async def close(self):
        if hasattr(self, 'session') and self.session:
            await self.session.close()
        await super().close()

@logger.catch
def main():
    bot = OsuBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
