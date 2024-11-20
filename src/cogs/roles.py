from discord.ext import commands, tasks
from discord.utils import get
from loguru import logger
from config import ROLES, REV_ROLES, ROLES_VALUE

from utils import get_role_with_rank, change_role, send_rolechange_msg


class RolesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.refresh_roles.start()

    def cog_unload(self):
        self.refresh_roles.cancel()

    @tasks.loop(minutes=15)
    async def refresh_roles(self):
        try:
            # ctx = self.bot.get_channel(BOT_CHANNEL_ID)
            async with self.bot.db.pool.acquire() as db:
                cursor = None
                ranking = []
                # get the first 1000 players from LV country leaderboard
                for i in range(20):
                    response = await self.bot.osuapi.get_rankings(
                        mode="osu", type="performance", country="LV", cursor=cursor
                    )
                    # print(response)
                    cursor = response["cursor"]["page"]
                    ranking.extend(response["ranking"])

                ranking_id_list = [x["user"]["id"] for x in ranking]

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

                    current_role = [
                        REV_ROLES[role.id]
                        for role in get(self.bot.lvguild.members, id=row[0]).roles
                        if role.id in ROLES.values()
                    ]

                    if country_rank == 99999:
                        osu_user = await self.bot.osuapi.get_user(
                            name=row[1], mode="osu", key="id"
                        )
                        if osu_user == {"error": None}:
                            osu_api_check = await self.bot.osuapi.get_user(
                                name=2, mode="osu", key="id"
                            )
                            if osu_api_check == {"error": None}:
                                continue
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
                                    osu_user=osu_user,
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
                                    osu_user=osu_user,
                                )
                            continue

                        if not osu_user["statistics"]["is_ranked"]:
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
        except Exception as e:
            logger.exception("error in refresh_roles")


async def setup(bot):
    await bot.add_cog(RolesCog(bot))
