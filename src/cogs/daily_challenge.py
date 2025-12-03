import asyncio
import discord
from discord.ext import commands, tasks
from loguru import logger
from config import BOT_CHANNEL_ID
from app import OsuBot
import re
import json
from html import unescape
from datetime import datetime, timedelta


class DailyChallengeCog(commands.Cog):
    def __init__(self, bot: OsuBot) -> None:
        self.bot = bot
        self.post_daily_challenge.start()

    async def cog_unload(self) -> None:
        self.post_daily_challenge.cancel()

    @tasks.loop(hours=24)
    async def post_daily_challenge(self) -> None:
        logger.info("Posting daily challenge")
        try:
            # Get today's date in YYYY-MM-DD format
            today = datetime.utcnow().date()
            date_str = today.strftime("%Y-%m-%d")

            url = f"https://osu.ppy.sh/rankings/daily-challenge/{date_str}"

            async with self.bot.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch daily challenge page: {response.status}")
                    return

                html = await response.text()

                # Extract JSON data from the HTML
                json_match = re.search(r'data-beatmapset-panel="([^"]*)"', html)
                if json_match:
                    json_str = unescape(json_match.group(1))
                    json_data = json.loads(json_str)
                    beatmapset_id = json_data['beatmapset']['id']
                    beatmapset_link = f"https://osu.ppy.sh/beatmapsets/{beatmapset_id}"
                    channel = self.bot.get_channel(BOT_CHANNEL_ID)
                    if channel and isinstance(channel, discord.TextChannel):
                        await channel.send(f"Today's Daily Challenge map: {beatmapset_link}")
                        logger.info(f"Posted daily challenge: {beatmapset_link}")
                    else:
                        logger.error("Could not find bot channel")
                else:
                    logger.error("Could not extract JSON data from daily challenge page")

        except Exception as e:
            logger.exception("Error posting daily challenge")

    @post_daily_challenge.before_loop
    async def before_post_daily_challenge(self) -> None:
        await self.bot.wait_until_ready()
        # Wait until 22:40 UTC (00:40 UTC+2) to start the loop
        now = datetime.utcnow()
        next_time = now.replace(hour=10, minute=40, second=0, microsecond=0)
        if next_time <= now:
            next_time += timedelta(days=1)
        seconds_until = (next_time - now).total_seconds()
        await asyncio.sleep(seconds_until)

    @discord.app_commands.command(
        name="daily_challenge", description="Get today's daily challenge map"
    )
    async def daily_challenge_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            # Get today's date in YYYY-MM-DD format
            today = datetime.utcnow().date()
            date_str = today.strftime("%Y-%m-%d")
            logger.info(f"Fetching daily challenge for date: {date_str}")

            url = f"https://osu.ppy.sh/rankings/daily-challenge/{date_str}"
            logger.info(f"URL: {url}")

            async with self.bot.session.get(url) as response:
                logger.info(f"Response status: {response.status}")
                if response.status != 200:
                    await interaction.followup.send(f"Failed to fetch daily challenge page: {response.status}")
                    return

                html = await response.text()
                logger.info(f"HTML length: {len(html)} characters")

                # Extract JSON data from the HTML
                json_match = re.search(r'data-beatmapset-panel="([^"]*)"', html)
                logger.info(f"JSON match found: {json_match is not None}")
                if json_match:
                    json_str = unescape(json_match.group(1))
                    json_data = json.loads(json_str)
                    beatmapset_id = json_data['beatmapset']['id']
                    beatmapset_link = f"https://osu.ppy.sh/beatmapsets/{beatmapset_id}"
                    logger.info(f"Extracted beatmapset link: {beatmapset_link}")
                    await interaction.followup.send(f"Today's Daily Challenge map: {beatmapset_link}")
                else:
                    logger.warning("Could not extract JSON data from daily challenge page")
                    await interaction.followup.send("Could not extract JSON data from daily challenge page")

        except Exception as e:
            logger.exception("Error fetching daily challenge")
            await interaction.followup.send("An error occurred while fetching the daily challenge.")


async def setup(bot: OsuBot) -> None:
    from config import SERVER_ID
    await bot.add_cog(DailyChallengeCog(bot), guild=discord.Object(id=SERVER_ID))
