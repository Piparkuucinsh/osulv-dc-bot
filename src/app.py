import sys
import asyncio
import queue
import discord
from discord.ext import commands
from ossapi import OssapiAsync
from db.db import Database
import aiohttp
from loguru import logger
from config import API_CLIENT_ID, API_CLIENT_SECRET, BOT_CHANNEL_ID

from config import DISCORD_TOKEN, SERVER_ID

# Queue for Discord log messages
_discord_log_queue: queue.Queue[str] = queue.Queue()

logger.add(
    lambda msg: _discord_log_queue.put_nowait(msg),
    level="WARNING",  # Only WARNING and above
    diagnose=False,
    backtrace=False,
    format="{time} | {level} | {message}\n{exception}",
)


class OsuBot(commands.Bot):
    osuapi: OssapiAsync
    db: Database
    lvguild: discord.Guild
    session: aiohttp.ClientSession
    _on_ready_finished: bool
    _log_task: asyncio.Task[None] | None

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.presences = True

        self.osuapi = OssapiAsync(API_CLIENT_ID, API_CLIENT_SECRET)
        self.db = Database()
        self._on_ready_finished = False
        self._log_task = None

        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        try:
            await self.db.setup_hook()
        except Exception as e:
            logger.exception("Database schema verification failed on startup: {}", e)
            # Shutdown gracefully to avoid running with an invalid schema
            try:
                await self.close()
            finally:
                # Re-raise so the process exits with a non-zero status
                raise

        # Load extensions - app commands are automatically registered when cogs are loaded
        await self.load_extension("cogs.events")
        await self.load_extension("cogs.commands")
        await self.load_extension("cogs.link_user")
        await self.load_extension("cogs.roles")
        await self.load_extension("cogs.user_newbest")

    async def on_ready(self) -> None:
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
        logger.info(
            f"Commands in tree before sync: {[cmd.name for cmd in all_commands]}"
        )

        # Sync commands to guild for instant availability
        # Note: sync() returns only NEWLY synced commands, not all commands
        # If commands are already synced, it returns an empty list
        try:
            guild_obj = discord.Object(id=SERVER_ID)
            synced = await self.tree.sync(guild=guild_obj)

            if len(synced) > 0:
                logger.info(
                    f"Synced {len(synced)} NEW command(s) to guild {SERVER_ID}: {[cmd.name for cmd in synced]}"
                )
            else:
                # Empty list means commands are already synced or no changes
                logger.info(
                    f"Commands already synced to guild {SERVER_ID} (or no changes detected)"
                )
                # Verify commands are actually available by checking the tree
                guild_commands = self.tree.get_commands(guild=guild_obj)
                logger.info(
                    f"Commands available in guild: {[cmd.name for cmd in guild_commands]}"
                )
        except discord.app_commands.CommandSyncFailure as e:
            logger.error(f"Command sync failure: {e}")
        except Exception as e:
            logger.exception(f"Failed to sync commands: {e}")

        # Run update_user before other tasks start
        # Import here to avoid circular import (utils imports from app)
        from utils import update_users_in_database

        try:
            logger.info("Running update_user on startup...")
            added_users = await update_users_in_database(self)
            if added_users:
                logger.info(
                    f"Startup update_user: Added {len(added_users)} user(s): {', '.join(m.name for m in added_users)}"
                )
        except Exception as e:
            # Log the error but don't fail startup - this is a non-critical operation
            # Database connection errors would have been caught earlier in setup_hook
            logger.exception(f"Failed to update users on startup: {e}")
            # Continue startup - the update_user command can be run manually if needed

        # Mark on_ready as finished
        self._on_ready_finished = True

        # Start Discord log processing task
        self._log_task = asyncio.create_task(self._process_discord_logs())

    async def _process_discord_logs(self) -> None:
        """Process log messages from queue and send to Discord channel.
        Sends up to 10 messages per second to respect rate limits."""
        while not self.is_closed():
            try:
                # Collect up to 10 messages from the queue
                messages: list[str] = []
                for _ in range(10):
                    try:
                        message = _discord_log_queue.get_nowait()
                        messages.append(str(message).strip())
                    except queue.Empty:
                        break

                # If we have messages, send them
                if messages:
                    channel = self.get_channel(BOT_CHANNEL_ID)
                    if channel and isinstance(channel, discord.TextChannel):
                        # Truncate each message if too long (Discord limit is 2000 chars)
                        # Account for code block markers: ```\n + \n``` = 7 chars
                        max_length = 2000 - 7  # Reserve space for code block markers
                        for message_text in messages:
                            if len(message_text) > max_length:
                                message_text = message_text[: max_length - 3] + "..."
                            await channel.send(f"```\n{message_text}\n```")

                # Wait 1 second before processing next batch (rate limit: 10 messages/second)
                await asyncio.sleep(1.0)
            except Exception as e:
                # Log to stderr if Discord logging fails to avoid infinite loop
                print(f"Error sending log to Discord: {e}", file=sys.stderr)
                await asyncio.sleep(1.0)

    async def close(self) -> None:
        if self._log_task:
            self._log_task.cancel()
            try:
                await self._log_task
            except asyncio.CancelledError:
                pass
        if hasattr(self, "session") and self.session:
            await self.session.close()
        await super().close()


@logger.catch
def main() -> None:
    bot = OsuBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
