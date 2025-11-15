import discord
from discord.ext import tasks
from discord.utils import get
from dateutil import parser
from datetime import datetime, timedelta, timezone
from rosu_pp_py import Beatmap, Performance, BeatmapAttributesBuilder
import time
import os
import aiohttp
from loguru import logger
from app import OsuBot
from utils import admin_or_role_check, BaseCog, wait_for_on_ready
from pathlib import Path

from config import (
    REV_ROLES,
    ROLES,
    ROLES_VALUE,
    USER_NEWBEST_LIMIT,
    BOTSPAM_CHANNEL_ID,
    RANK_EMOJI,
    SERVER_ID,
)
from ossapi import GameMode, ScoreType, UserLookupKey
from ossapi.models import Score, User, NonLegacyMod
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ossapi.models import Mod


class UserNewbest(BaseCog):
    def __init__(self, bot: OsuBot) -> None:
        self.bot = bot
        self.user_newbest_loop.start()

    async def cog_unload(self) -> None:
        self.user_newbest_loop.cancel()

    @discord.app_commands.command(
        name="start_userbest", description="Manually trigger the user newbest check"
    )
    @discord.app_commands.check(admin_or_role_check)
    async def start_userbest(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer()
            await self.user_newbest_loop()
            await interaction.followup.send(
                "User newbest check completed successfully."
            )
        except Exception as e:
            # logger.error(repr(e))
            logger.exception("error in start_userbest")
            if interaction.response.is_done():
                await interaction.followup.send(f"{repr(e)} in userbest")
            else:
                await interaction.response.send_message(f"{repr(e)} in userbest")

    @tasks.loop(minutes=60)
    async def user_newbest_loop(self) -> None:
        try:
            logger.info("Starting user_newbest_loop task execution")
            async with self.bot.db.pool.acquire() as db:
                result = await db.fetch(
                    "SELECT * FROM players WHERE osu_id IS NOT NULL;"
                )
                member_id_list = [x.id for x in self.bot.lvguild.members]

                for row in result:
                    try:
                        if row[0] not in member_id_list:
                            continue

                        member = get(self.bot.lvguild.members, id=row[0])
                        if member is None:
                            raise ValueError(
                                f"user_newbest_loop: Member {row[0]} not found in guild"
                            )
                        current_roles = [
                            REV_ROLES[role.id]
                            for role in member.roles
                            if role.id in ROLES.values()
                        ]
                        if not current_roles:
                            continue
                        current_role = current_roles[0]
                        if ROLES_VALUE[current_role] > 9:
                            continue

                        if row[2] is None:
                            last_checked = datetime.now(tz=timezone.utc) - timedelta(
                                minutes=60
                            )
                        else:
                            last_checked = parser.parse(row[2])

                        limit = USER_NEWBEST_LIMIT[current_role]

                        await self.get_user_newbest(
                            osu_id=row[1], limit=limit, last_checked=last_checked
                        )

                        await db.execute(
                            f"UPDATE players SET last_checked = '{datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()}' WHERE discord_id = {row[0]}"
                        )

                        time.sleep(0.1)

                    except Exception:
                        logger.exception(
                            f"error in user_newbest_loop while processing user with discord id {row[0]} and osu id {row[1]}"
                        )
                        continue

                logger.info("user_newbest_loop finished")
        except Exception:
            logger.exception("error in user_newbest_loop")

    @user_newbest_loop.before_loop
    async def before_user_newbest(self) -> None:
        await self.bot.wait_until_ready()
        await wait_for_on_ready(self.bot)

    async def get_user_newbest(
        self, osu_id: int, limit: int, last_checked: datetime
    ) -> None:
        user_scores = await self.bot.osuapi.user_scores(
            osu_id,
            type=ScoreType.BEST,
            include_fails=False,
            limit=limit,
            mode=GameMode.OSU,
        )
        osu_user = None
        score_ids = []
        for index, score in enumerate(user_scores, start=1):
            score_time = score.ended_at
            if isinstance(score_time, str):
                score_time = parser.parse(score_time)
            if score_time > last_checked:
                if osu_user is None:
                    osu_user = await self.bot.osuapi.user(
                        osu_id, mode=GameMode.OSU, key=UserLookupKey.ID
                    )
                await self.post_user_newbest(
                    score=score,
                    limit=limit,
                    scoretime=score_time,
                    score_rank=index,
                    osu_user=osu_user,
                )
                if score.id is not None:
                    score_ids.append(str(score.id))

        if len(score_ids) > 0:
            logger.info(
                f"posted {len(score_ids)} ({', '.join(score_ids)}) new best scores for {osu_user.username if osu_user else ''} ({osu_id})"
            )

    async def post_user_newbest(
        self,
        score: Score,
        score_rank: int,
        limit: int,
        scoretime: datetime,
        osu_user: User,
    ) -> None:
        channel = self.bot.get_channel(BOTSPAM_CHANNEL_ID)
        if not channel or not isinstance(channel, discord.TextChannel):
            raise ValueError(
                f"post_user_newbest: Channel {BOTSPAM_CHANNEL_ID} not found or is not a text channel"
            )
        embed_color = 0x0084FF

        if score.ruleset_id != 0:
            raise ValueError(
                f"Score is not osu! standard mode (ruleset_id: {score.ruleset_id})"
            )
        if score.beatmap is None:
            raise ValueError("Score beatmap is missing")
        if score.beatmapset is None:
            raise ValueError("Score beatmapset is missing")
        if osu_user.statistics is None:
            raise ValueError("User statistics is missing")

        beatmap_id = score.beatmap_id

        path = Path(os.getcwd(), "beatmaps", f"{beatmap_id}.osu")

        if not path.exists():
            async with aiohttp.ClientSession() as s:
                url = f"https://osu.ppy.sh/osu/{beatmap_id}"
                async with s.get(url) as resp:
                    if resp.status == 200:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with path.open(
                            mode="wb",
                        ) as f:
                            f.write(await resp.read())

        with path.open(mode="rb") as f:
            beatmap = Beatmap(bytes=f.read())

        perf = Performance(lazer=False)
        mapattr = BeatmapAttributesBuilder()

        score_mods = score.mods
        perf.set_mods(mods=[{"acronym": mod.acronym} for mod in score_mods])
        calc_result = perf.calculate(beatmap)

        mapattr.set_map(beatmap)
        map_attrs = mapattr.build()

        total_length = score.beatmap.total_length
        time_text = (
            str(timedelta(seconds=total_length)).removeprefix("0:")
            if map_attrs.clock_rate == 1
            else f"{str(timedelta(seconds=total_length)).removeprefix('0:')} ({str(timedelta(seconds=round(total_length / map_attrs.clock_rate))).removeprefix('0:')})"
        )
        bpm = score.beatmap.bpm
        if bpm is None:
            raise ValueError("Score beatmap BPM is missing")
        bpm_text = (
            f"{bpm} BPM"
            if map_attrs.clock_rate == 1
            else f"{bpm} -> **{round(int(bpm) * map_attrs.clock_rate)} BPM**"
        )
        if score_mods:
            mod_text = "\t+"
            for mod in score_mods:
                name = mod.acronym
                mod_text += name
        else:
            mod_text = ""

        desc = f"**__Personal Best #{score_rank}__**"

        embed = discord.Embed(description=desc, color=embed_color)

        country_code = osu_user.country_code
        if osu_user.statistics.pp is None:
            raise ValueError("User statistics PP is missing")
        pp = round(osu_user.statistics.pp, 2)
        global_rank = osu_user.statistics.global_rank or 0
        country_rank = osu_user.statistics.country_rank or 0
        user_id = osu_user.id
        username = osu_user.username
        avatar_url = osu_user.avatar_url
        embed.set_author(
            name=f"{username}: {pp:,}pp (#{global_rank:,} {country_code}{country_rank})",
            url=f"https://osu.ppy.sh/users/{user_id}",
            icon_url=avatar_url,
        )
        covers_url = score.beatmapset.covers.list
        if covers_url:
            embed.set_thumbnail(url=covers_url)
        embed.url = f"https://osu.ppy.sh/b/{beatmap_id}"
        artist = score.beatmapset.artist
        title = score.beatmapset.title
        version = score.beatmap.version
        embed.title = f"{artist} - {title} [{version}] [{round(calc_result.difficulty.stars, 2)}★]"

        rank_key = score.rank.value

        # Score.statistics is a Statistics object (current format)
        s_stats = score.statistics
        c300 = s_stats.great or 0
        c100 = s_stats.ok or 0
        c50 = s_stats.meh or 0
        cmiss = s_stats.miss or 0
        # Score uses legacy_total_score if available and not 0, otherwise total_score
        total_score = (
            score.legacy_total_score
            if score.legacy_total_score is not None and score.legacy_total_score != 0
            else score.total_score
        )
        accuracy = score.accuracy
        pp_value = score.pp or 0.0
        max_combo = score.max_combo
        embed.add_field(
            name=f"** {RANK_EMOJI.get(rank_key, '')}{mod_text}\t{total_score:,}\t({round(accuracy, 4):.2%}) **",
            value=f"""**{round(pp_value, 2)}**/{round(calc_result.pp, 2)}pp [ **{max_combo}x**/{calc_result.difficulty.max_combo}x ] {{{c300}/{c100}/{c50}/{cmiss}}}
            {time_text} | {bpm_text}
            <t:{int(scoretime.timestamp())}:R> | Limit: {limit}""",
        )

        await channel.send(embed=embed)


async def setup(bot: OsuBot) -> None:
    await bot.add_cog(UserNewbest(bot), guild=discord.Object(id=SERVER_ID))
