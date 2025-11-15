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
from utils import mods_int_from_list, admin_or_role_check, BaseCog, wait_for_on_ready
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


class UserNewbest(BaseCog):
    def __init__(self, bot):
        self.bot = bot
        self.user_newbest_loop.start()

    async def cog_unload(self):
        self.user_newbest_loop.cancel()

    @discord.app_commands.command(name="start_userbest", description="Manually trigger the user newbest check")
    @discord.app_commands.check(admin_or_role_check)
    async def start_userbest(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            await self.user_newbest_loop()
            await interaction.followup.send("User newbest check completed successfully.")
        except Exception as e:
            # logger.error(repr(e))
            logger.exception("error in start_userbest")
            if interaction.response.is_done():
                await interaction.followup.send(f"{repr(e)} in userbest")
            else:
                await interaction.response.send_message(f"{repr(e)} in userbest")

    @tasks.loop(minutes=60)
    async def user_newbest_loop(self):
        async with self.bot.db.pool.acquire() as db:
            result = await db.fetch("SELECT * FROM players WHERE osu_id IS NOT NULL;")
            member_id_list = [x.id for x in self.bot.lvguild.members]

            for row in result:
                if row[0] not in member_id_list:
                    continue

                current_roles = [
                    REV_ROLES[role.id]
                    for role in get(self.bot.lvguild.members, id=row[0]).roles
                    if role.id in ROLES.values()
                ]
                if not current_roles:
                    continue
                current_role = current_roles[0]
                if ROLES_VALUE[current_role] > 9:
                    continue

                if row[2] is None:
                    last_checked = datetime.now(tz=timezone.utc) - timedelta(minutes=60)
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

            logger.info("user_newbest_loop finished")

    @user_newbest_loop.before_loop
    async def before_user_newbest(self):
        await self.bot.wait_until_ready()
        await wait_for_on_ready(self.bot)

    async def get_user_newbest(self, osu_id, limit, last_checked):
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
            score_time = getattr(score, "created_at", None)
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
                score_ids.append(str(getattr(score, "id", "")))

        if len(score_ids) > 0:
            logger.info(
                f"posted {len(score_ids)} ({', '.join(score_ids)}) new best scores for {osu_user.username if osu_user else ''} ({osu_id})"
            )

    async def post_user_newbest(self, score, score_rank, limit, scoretime, osu_user):
        channel = self.bot.get_channel(BOTSPAM_CHANNEL_ID)
        embed_color = 0x0084FF

        beatmap_id = score.beatmap.id

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

        perf.set_mods(mods=await mods_int_from_list(score.mods))
        calc_result = perf.calculate(beatmap)

        mapattr.set_map(beatmap)
        map_attrs = mapattr.build()

        total_length = getattr(score.beatmap, "total_length", 0)
        time_text = (
            str(timedelta(seconds=total_length)).removeprefix("0:")
            if map_attrs.clock_rate == 1
            else f"{str(timedelta(seconds=total_length)).removeprefix('0:')} ({str(timedelta(seconds=round(total_length/map_attrs.clock_rate))).removeprefix('0:')})"
        )
        bpm = getattr(score.beatmap, "bpm", 0)
        bpm_text = (
            f"{bpm} BPM"
            if map_attrs.clock_rate == 1
            else f"{bpm} -> **{round(int(bpm)*map_attrs.clock_rate)} BPM**"
        )
        if getattr(score, "mods", []) != []:
            mod_text = "\t+"
            for mod in score.mods:
                name = getattr(mod, "acronym", getattr(mod, "name", str(mod)))
                mod_text += name
        else:
            mod_text = ""

        desc = f"**__Personal Best #{score_rank}__**"

        embed = discord.Embed(description=desc, color=embed_color)

        user = score.user
        country_code = getattr(user, "country_code", getattr(user.country, "code", ""))
        pp = round(getattr(osu_user.statistics, "pp", 0.0), 2)
        global_rank = getattr(osu_user.statistics, "global_rank", 0) or 0
        country_rank = getattr(osu_user.statistics, "country_rank", 0) or 0
        embed.set_author(
            name=f"{user.username}: {pp:,}pp (#{global_rank:,} {country_code}{country_rank})",
            url=f"https://osu.ppy.sh/users/{user.id}",
            icon_url=user.avatar_url,
        )
        covers_list = getattr(getattr(score, "beatmapset", None), "covers", None)
        covers_url = getattr(covers_list, "list", None) if covers_list else None
        if covers_url:
            embed.set_thumbnail(url=covers_url)
        embed.url = f"https://osu.ppy.sh/b/{score.beatmap.id}"
        embed.title = f"{getattr(score.beatmapset, 'artist', '')} - {getattr(score.beatmapset, 'title', '')} [{getattr(score.beatmap, 'version', '')}] [{round(calc_result.difficulty.stars, 2)}★]"

        rank_key = getattr(score, "rank", None)
        if rank_key is not None and hasattr(rank_key, "value"):
            rank_key = rank_key.value
        else:
            rank_key = str(rank_key) if rank_key is not None else ""
        s_stats = getattr(score, "statistics", None) or getattr(score, "legacy_statistics", None)
        c300 = getattr(s_stats, "count_300", getattr(score, "count_300", 0))
        c100 = getattr(s_stats, "count_100", getattr(score, "count_100", 0))
        c50 = getattr(s_stats, "count_50", getattr(score, "count_50", 0))
        cmiss = getattr(s_stats, "count_miss", getattr(score, "count_miss", 0))
        embed.add_field(
            name=f"** {RANK_EMOJI.get(rank_key, '')}{mod_text}\t{getattr(score, 'score', 0):,}\t({round(getattr(score, 'accuracy', 0.0), 4):.2%}) **",
            value=f"""**{round(getattr(score, 'pp', 0.0) or 0.0, 2)}**/{round(calc_result.pp, 2)}pp [ **{getattr(score, 'max_combo', 0)}x**/{calc_result.difficulty.max_combo}x ] {{{c300}/{c100}/{c50}/{cmiss}}}
            {time_text} | {bpm_text}
            <t:{int(scoretime.timestamp())}:R> | Limit: {limit}""",
        )

        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(UserNewbest(bot), guild=discord.Object(id=SERVER_ID))
