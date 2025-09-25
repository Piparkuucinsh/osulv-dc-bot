from typing import Dict, List, Optional

from discord.ext import commands, tasks
from discord.utils import get
from loguru import logger
from config import ROLES, REV_ROLES, ROLES_VALUE

from utils import get_role_with_rank, change_role, send_rolechange_msg
from ossapi import GameMode, RankingType, UserLookupKey


class RolesCog(commands.Cog):
    """Cog responsible for periodically refreshing member roles based on osu! ranks.

    The loop fetches the Latvia leaderboard, maps osu! user ids to their country rank,
    and adjusts Discord roles accordingly, including handling restricted/inactive users.
    """

    def __init__(self, bot):
        self.bot = bot
        self.refresh_roles.start()

    def cog_unload(self):
        self.refresh_roles.cancel()

    @tasks.loop(minutes=15)
    async def refresh_roles(self):
        """Refresh roles for all linked players in the guild.

        - Fetches top 1000 LV players and builds an id->rank lookup
        - Iterates through linked players present in the guild
        - Applies role transitions and sends announcement messages
        """
        try:
            async with self.bot.db.pool.acquire() as db:
                # Build a mapping of osu user id -> country rank for faster lookups
                ranking: List = []
                for page in range(1, 21):  # 20 pages * 50 users per page = 1000
                    resp = await self.bot.osuapi.rankings(
                        GameMode.OSU, RankingType.PERFORMANCE, country="LV", page=page
                    )
                    ranking.extend(resp.ranking)

                id_to_country_rank: Dict[int, int] = {
                    entry.user.id: index + 1 for index, entry in enumerate(ranking)
                }

                rows = await db.fetch(
                    "SELECT discord_id, osu_id FROM players WHERE osu_id IS NOT NULL;"
                )
                guild_member_ids = {member.id for member in self.bot.lvguild.members}

                for discord_id, osu_id in rows:
                    if discord_id not in guild_member_ids:
                        continue

                    country_rank: int = id_to_country_rank.get(osu_id, 99999)

                    # Handle restricted / inactive only if not found on LV leaderboard
                    if country_rank == 99999:
                        try:
                            osu_user = await self.bot.osuapi.user(
                                osu_id, mode=GameMode.OSU, key=UserLookupKey.ID
                            )
                        except Exception:
                            osu_user = None

                        if osu_user is None:
                            await self._set_role_and_announce(
                                discord_id=discord_id,
                                new_role_name="restricted",
                                osu_id=osu_id,
                                osu_user=None,
                            )
                            continue

                        is_ranked = getattr(osu_user.statistics, "is_ranked", True)
                        if not is_ranked:
                            await self._set_role_and_announce(
                                discord_id=discord_id,
                                new_role_name="inactive",
                                osu_id=osu_id,
                                osu_user=osu_user,
                            )
                            continue

                    # Otherwise proceed with rank-based roles
                    new_role_name = await get_role_with_rank(country_rank)
                    await self._set_role_and_announce(
                        discord_id=discord_id,
                        new_role_name=new_role_name,
                        osu_id=osu_id,
                    )

            logger.info("roles refreshed")
        except Exception:
            logger.exception("error in refresh_roles")

    async def _set_role_and_announce(
        self,
        *,
        discord_id: int,
        new_role_name: str,
        osu_id: Optional[int] = None,
        osu_user: Optional[object] = None,
    ) -> None:
        """Determine current role, set new role, and announce with proper event.

        This decides between: no_previous_role, unrestricted, pacelas (rose),
        nokritas (fell), restricted, inactive.
        """
        member = get(self.bot.lvguild.members, id=discord_id)
        current_role_names: List[str] = [
            REV_ROLES[role.id] for role in member.roles if role.id in ROLES.values()
        ]

        # Special cases pushed by callers
        if new_role_name in {"restricted", "inactive"}:
            if current_role_names == []:
                await change_role(
                    bot=self.bot, discord_id=discord_id, new_role_id=ROLES[new_role_name]
                )
            else:
                await change_role(
                    bot=self.bot,
                    discord_id=discord_id,
                    current_role_id=ROLES[current_role_names[0]],
                    new_role_id=ROLES[new_role_name],
                )
            await send_rolechange_msg(
                bot=self.bot,
                discord_id=discord_id,
                notikums=new_role_name,
                osu_id=osu_id,
                osu_user=osu_user,
            )
            return

        # Rank-based role changes
        if current_role_names == []:
            await change_role(
                bot=self.bot, discord_id=discord_id, new_role_id=ROLES[new_role_name]
            )
            await send_rolechange_msg(
                bot=self.bot,
                discord_id=discord_id,
                notikums="no_previous_role",
                role=new_role_name,
                osu_id=osu_id,
                osu_user=osu_user,
            )
            return

        current = current_role_names[0]

        if current == "restricted":
            await change_role(
                bot=self.bot,
                discord_id=discord_id,
                current_role_id=ROLES[current],
                new_role_id=ROLES[new_role_name],
            )
            await send_rolechange_msg(
                bot=self.bot,
                discord_id=discord_id,
                notikums="unrestricted",
                role=new_role_name,
                osu_id=osu_id,
                osu_user=osu_user,
            )
            return

        if new_role_name == current:
            return

        if ROLES_VALUE[new_role_name] < ROLES_VALUE[current]:
            # Rose in rank
            await change_role(
                bot=self.bot,
                discord_id=discord_id,
                current_role_id=ROLES[current],
                new_role_id=ROLES[new_role_name],
            )
            await send_rolechange_msg(
                bot=self.bot,
                discord_id=discord_id,
                notikums="pacelas",
                role=new_role_name,
                osu_id=osu_id,
                osu_user=osu_user,
            )
            return

        if ROLES_VALUE[new_role_name] > ROLES_VALUE[current]:
            # Fell in rank
            await change_role(
                bot=self.bot,
                discord_id=discord_id,
                current_role_id=ROLES[current],
                new_role_id=ROLES[new_role_name],
            )
            await send_rolechange_msg(
                bot=self.bot,
                discord_id=discord_id,
                notikums="nokritas",
                role=new_role_name,
                osu_id=osu_id,
                osu_user=osu_user,
            )
            return


async def setup(bot):
    await bot.add_cog(RolesCog(bot))
