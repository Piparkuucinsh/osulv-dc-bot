import discord
from discord.ext import commands, tasks
from discord.utils import get
from dateutil import parser
from datetime import datetime, timedelta, timezone
from rosu_pp_py import Beatmap, Performance, BeatmapAttributesBuilder
import time
import os
import aiohttp
from loguru import logger
from utils import mods_int_from_list
from pathlib import Path

from config import (
    REV_ROLES,
    ROLES,
    ROLES_VALUE,
    USER_NEWBEST_LIMIT,
    BOTSPAM_CHANNEL_ID,
    RANK_EMOJI,
)


class UserNewbest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_newbest_loop.start()

    def cog_unload(self):
        self.user_newbest_loop.cancel()

    @commands.command()
    async def start_userbest(self, ctx):
        try:
            await self.user_newbest_loop()
        except Exception as e:
            # logger.error(repr(e))
            logger.exception("error in start_userbest")
            await ctx.send(f"{repr(e)} in userbest")

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

    async def get_user_newbest(self, osu_id, limit, last_checked):
        user_scores = await self.bot.osuapi.get_scores(
            osu_id=osu_id, type="best", mode="osu", limit=limit
        )
        osu_user = None
        score_ids = []
        for index, score in enumerate(user_scores, start=1):
            score_time = parser.parse(score["created_at"])
            if score_time > last_checked:
                if osu_user is None:
                    osu_user = await self.bot.osuapi.get_user(
                        name=osu_id, mode="osu", key="id"
                    )
                await self.post_user_newbest(
                    score=score,
                    limit=limit,
                    scoretime=score_time,
                    score_rank=index,
                    osu_user=osu_user,
                )
                score_ids.append(str(score["id"]))

        if len(score_ids) > 0:
            logger.info(
                f"posted {len(score_ids)} ({', '.join(score_ids)}) new best scores for {osu_user['username'] if osu_user else ''} ({osu_id})"
            )

    async def post_user_newbest(self, score, score_rank, limit, scoretime, osu_user):
        channel = self.bot.get_channel(BOTSPAM_CHANNEL_ID)
        embed_color = 0x0084FF

        beatmap_id = score["beatmap"]["id"]

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

        perf = Performance()
        mapattr = BeatmapAttributesBuilder()

        perf.set_mods(mods=await mods_int_from_list(score["mods"]))
        calc_result = perf.calculate(beatmap)

        mapattr.set_map(beatmap)
        map_attrs = mapattr.build()

        time_text = (
            str(timedelta(seconds=score["beatmap"]["total_length"])).removeprefix("0:")
            if map_attrs.clock_rate == 1
            else f"{str(timedelta(seconds=score['beatmap']['total_length'])).removeprefix('0:')} ({str(timedelta(seconds=round(score['beatmap']['total_length']/map_attrs.clock_rate))).removeprefix('0:')})"
        )
        bpm_text = (
            f'{score["beatmap"]["bpm"]} BPM'
            if map_attrs.clock_rate == 1
            else f'{score["beatmap"]["bpm"]} -> **{round(int(score["beatmap"]["bpm"])*map_attrs.clock_rate)} BPM**'
        )
        if score["mods"] != []:
            mod_text = "\t+"
            for mod in score["mods"]:
                mod_text += mod
        else:
            mod_text = ""

        desc = f"**__Personal Best #{score_rank}__**"

        embed = discord.Embed(description=desc, color=embed_color)

        embed.set_author(
            name=f'{score["user"]["username"]}: {round(osu_user["statistics"]["pp"], 2):,}pp (#{osu_user["statistics"]["global_rank"]:,} {score["user"]["country_code"]}{osu_user["statistics"]["country_rank"]})',
            url=f'https://osu.ppy.sh/users/{score["user"]["id"]}',
            icon_url=score["user"]["avatar_url"],
        )
        embed.set_thumbnail(url=score["beatmapset"]["covers"]["list"])
        embed.url = f'https://osu.ppy.sh/b/{score["beatmap"]["id"]}'
        embed.title = f'{score["beatmapset"]["artist"]} - {score["beatmapset"]["title"]} [{score["beatmap"]["version"]}] [{round(calc_result.difficulty.stars, 2)}★]'

        embed.add_field(
            name=f'** {RANK_EMOJI[score["rank"]]}{mod_text}\t{score["score"]:,}\t({round(score["accuracy"], 4):.2%}) **',
            value=f"""**{round(score["pp"], 2)}**/{round(calc_result.pp, 2)}pp [ **{score["max_combo"]}x**/{calc_result.difficulty.max_combo}x ] {{{score["statistics"]["count_300"]}/{score["statistics"]["count_100"]}/{score["statistics"]["count_50"]}/{score["statistics"]["count_miss"]}}}
            {time_text} | {bpm_text}
            <t:{int(scoretime.timestamp())}:R> | Limit: {limit}""",
        )

        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(UserNewbest(bot))
