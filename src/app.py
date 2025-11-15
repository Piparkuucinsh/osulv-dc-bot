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
    _on_ready_finished: bool

    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.presences = True

        self.osuapi = OsuApiV2()
        self.db = Database()
        self._on_ready_finished = False

        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.osuapi.session = self.session
        await self.osuapi.refresh_token()
        await self.db.setup_hook()
        
        # Load extensions - app commands are automatically registered when cogs are loaded
        await self.load_extension("cogs.events")
        await self.load_extension("cogs.commands")
        await self.load_extension("cogs.link_user")
        await self.load_extension("cogs.roles")
        await self.load_extension("cogs.user_newbest")

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
        
        # Debug: Log all commands in the tree before syncing
        all_commands = self.tree.get_commands()
        logger.info(f"Commands in tree before sync: {[cmd.name for cmd in all_commands]}")
        
        # Sync commands to guild for instant availability
        # Note: sync() returns only NEWLY synced commands, not all commands
        # If commands are already synced, it returns an empty list
        try:
            guild_obj = discord.Object(id=SERVER_ID)
            synced = await self.tree.sync(guild=guild_obj)
            
            if len(synced) > 0:
                logger.info(f"Synced {len(synced)} NEW command(s) to guild {SERVER_ID}: {[cmd.name for cmd in synced]}")
            else:
                # Empty list means commands are already synced or no changes
                logger.info(f"Commands already synced to guild {SERVER_ID} (or no changes detected)")
                # Verify commands are actually available by checking the tree
                guild_commands = self.tree.get_commands(guild=guild_obj)
                logger.info(f"Commands available in guild: {[cmd.name for cmd in guild_commands]}")
        except discord.app_commands.CommandSyncFailure as e:
            logger.error(f"Command sync failure: {e}")
        except Exception as e:
            logger.exception(f"Failed to sync commands: {e}")
        
        # Mark on_ready as finished
        self._on_ready_finished = True

    async def close(self):
        if hasattr(self, "session") and self.session:
            await self.session.close()
        await super().close()


@logger.catch
def main():
    bot = OsuBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
