from discord.ext import commands, tasks
from discord.utils import get
from loguru import logger
from config import ROLES, REV_ROLES, ROLES_VALUE
from app import OsuBot

from utils import (
    get_role_with_rank,
    change_role,
    send_rolechange_msg,
    wait_for_on_ready,
)
from ossapi import GameMode, RankingType, UserLookupKey, Cursor


class RolesCog(commands.Cog):
    def __init__(self, bot: OsuBot) -> None:
        self.bot = bot
        self.refresh_roles.start()

    async def cog_unload(self) -> None:
        self.refresh_roles.cancel()

    @tasks.loop(minutes=15)
    async def refresh_roles(self) -> None:
        try:
            # ctx = self.bot.get_channel(BOT_CHANNEL_ID)
            async with self.bot.db.pool.acquire() as db:
                ranking = []
                # get the first 1000 players from LV country leaderboard
                cursor = None
                for i in range(20):
                    resp = await self.bot.osuapi.ranking(
                        GameMode.OSU,
                        RankingType.PERFORMANCE,
                        country="LV",
                        cursor=cursor,
                    )
                    ranking.extend(resp.ranking)
                    # Stop if we got no results (last page)
                    if len(resp.ranking) == 0:
                        break
                    # Use cursor from response for next page, or fallback to page-based pagination
                    if resp.cursor is not None:
                        cursor = resp.cursor
                    else:
                        # Fallback to page-based pagination if cursor not available
                        cursor = Cursor(page=i + 2)

                ranking_id_list = [x.user.id for x in ranking]

                result = await db.fetch(
                    "SELECT discord_id, osu_id FROM players WHERE osu_id IS NOT NULL;"
                )

                member_id_list = [x.id for x in self.bot.lvguild.members]

                for row in result:
                    if row[0] not in member_id_list:
                        continue
                    try:
                        country_rank = ranking_id_list.index(row[1]) + 1
                    except ValueError:
                        country_rank = 99999

                    member = get(self.bot.lvguild.members, id=row[0])
                    if member is None:
                        continue
                    current_role = [
                        REV_ROLES[role.id]
                        for role in member.roles
                        if role.id in ROLES.values()
                    ]

                    if country_rank == 99999:
                        try:
                            osu_user = await self.bot.osuapi.user(
                                row[1], mode=GameMode.OSU, key=UserLookupKey.ID
                            )
                        except Exception:
                            osu_user = None
                        if osu_user is None:
                            if current_role == []:
                                await change_role(
                                    bot=self.bot,
                                    discord_id=row[0],
                                    new_role_id=ROLES["restricted"],
                                )
                                await send_rolechange_msg(
                                    bot=self.bot,
                                    discord_id=row[0],
                                    notikums="restricted",
                                    osu_user=None,
                                )
                                continue
                            if ROLES[current_role[0]] != ROLES["restricted"]:
                                await change_role(
                                    bot=self.bot,
                                    discord_id=row[0],
                                    current_role_id=ROLES[current_role[0]],
                                    new_role_id=ROLES["restricted"],
                                )
                                await send_rolechange_msg(
                                    bot=self.bot,
                                    discord_id=row[0],
                                    notikums="restricted",
                                    osu_user=None,
                                )
                            continue

                        is_ranked = getattr(osu_user.statistics, "is_ranked", True)
                        if not is_ranked:
                            if current_role == []:
                                await change_role(
                                    bot=self.bot,
                                    discord_id=row[0],
                                    new_role_id=ROLES["inactive"],
                                )
                                await send_rolechange_msg(
                                    bot=self.bot,
                                    discord_id=row[0],
                                    notikums="inactive",
                                    osu_user=osu_user,
                                )
                                continue
                            if ROLES[current_role[0]] != ROLES["inactive"]:
                                await change_role(
                                    bot=self.bot,
                                    discord_id=row[0],
                                    current_role_id=ROLES[current_role[0]],
                                    new_role_id=ROLES["inactive"],
                                )
                                await send_rolechange_msg(
                                    bot=self.bot,
                                    discord_id=row[0],
                                    notikums="inactive",
                                    osu_user=osu_user,
                                )
                            continue

                    new_role = await get_role_with_rank(country_rank)

                    if current_role == []:
                        await change_role(
                            bot=self.bot, discord_id=row[0], new_role_id=ROLES[new_role]
                        )
                        await send_rolechange_msg(
                            bot=self.bot,
                            discord_id=row[0],
                            notikums="no_previous_role",
                            role=new_role,
                            osu_id=row[1],
                        )

                    elif current_role[0] == "restricted":
                        await change_role(
                            bot=self.bot,
                            discord_id=row[0],
                            current_role_id=ROLES[current_role[0]],
                            new_role_id=ROLES[new_role],
                        )
                        await send_rolechange_msg(
                            bot=self.bot,
                            discord_id=row[0],
                            notikums="unrestricted",
                            role=new_role,
                            osu_id=row[1],
                        )

                    elif new_role != current_role[0]:
                        if ROLES_VALUE[new_role] < ROLES_VALUE[current_role[0]]:
                            await change_role(
                                bot=self.bot,
                                discord_id=row[0],
                                current_role_id=ROLES[current_role[0]],
                                new_role_id=ROLES[new_role],
                            )
                            await send_rolechange_msg(
                                bot=self.bot,
                                discord_id=row[0],
                                notikums="pacelas",
                                role=new_role,
                                osu_id=row[1],
                            )
                            continue
                        if ROLES_VALUE[new_role] > ROLES_VALUE[current_role[0]]:
                            await change_role(
                                bot=self.bot,
                                discord_id=row[0],
                                current_role_id=ROLES[current_role[0]],
                                new_role_id=ROLES[new_role],
                            )
                            await send_rolechange_msg(
                                bot=self.bot,
                                discord_id=row[0],
                                notikums="nokritas",
                                role=new_role,
                                osu_id=row[1],
                            )
                            continue

            logger.info("roles refreshed")
        except Exception:
            logger.exception("error in refresh_roles")

    @refresh_roles.before_loop
    async def before_refresh_roles(self) -> None:
        await self.bot.wait_until_ready()
        await wait_for_on_ready(self.bot)


async def setup(bot: OsuBot) -> None:
    await bot.add_cog(RolesCog(bot))
