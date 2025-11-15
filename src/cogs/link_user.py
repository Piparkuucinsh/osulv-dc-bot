import discord
from discord.ext import commands, tasks
from discord.utils import get
from loguru import logger

from app import OsuBot
from utils import refresh_user_rank, wait_for_on_ready
from ossapi import GameMode, UserLookupKey

from config import BOT_CHANNEL_ID, POST_REQUEST_URL, POST_REQUEST_TOKEN

OSU_APPLICATION_ID = 367827983903490050
IMMIGRANT_ROLE_ID = 539951111382237198


class LinkUser(commands.Cog):
    def __init__(self, bot: OsuBot) -> None:
        self.bot = bot
        self.already_sent_messages: list[tuple[int, int]] = []
        self.link_acc.start()

    async def cog_unload(self) -> None:
        self.link_acc.cancel()

    @tasks.loop(minutes=5)
    async def link_acc(self) -> None:
        ctx: discord.TextChannel | None = None
        try:
            channel = self.bot.get_channel(BOT_CHANNEL_ID)
            if not isinstance(channel, discord.TextChannel):
                raise ValueError(
                    f"Channel {BOT_CHANNEL_ID} not found or is not a text channel"
                )
            ctx = channel
            async with self.bot.db.pool.acquire() as db:
                for guild in self.bot.guilds:
                    for member in guild.members:
                        if member.activities is not None:
                            for osu_activity in member.activities:
                                try:
                                    if not hasattr(osu_activity, "application_id"):
                                        continue
                                    if (
                                        getattr(osu_activity, "application_id", None)
                                        == OSU_APPLICATION_ID
                                    ):
                                        if not hasattr(
                                            osu_activity, "large_image_text"
                                        ):
                                            continue

                                        large_image_text = getattr(
                                            osu_activity, "large_image_text", None
                                        )
                                        if large_image_text is None:
                                            continue

                                        username = large_image_text.split("(", 1)[
                                            0
                                        ].removesuffix(" ")
                                        if username == large_image_text:
                                            continue

                                        try:
                                            osu_user = await self.bot.osuapi.user(
                                                username,
                                                mode=GameMode.OSU,
                                                key=UserLookupKey.USERNAME,
                                            )
                                        except Exception:
                                            continue

                                        queryString = f"SELECT discord_id, osu_id FROM players WHERE discord_id = {member.id} AND osu_id IS NOT NULL"

                                        result = await db.fetch(queryString)
                                        if result == []:
                                            in_db_check = await db.fetch(
                                                f"SELECT discord_id FROM players WHERE discord_id = {member.id}"
                                            )
                                            if in_db_check == []:
                                                logger.warning(
                                                    f"link_user: discord member {member.id} not in db"
                                                )
                                                continue

                                            country_code = getattr(
                                                osu_user,
                                                "country_code",
                                                getattr(osu_user.country, "code", None),
                                            )
                                            if country_code == "LV":
                                                result = await db.fetch(
                                                    f"SELECT discord_id, osu_id FROM players WHERE osu_id = {osu_user.id};"
                                                )
                                                if result == []:
                                                    await db.execute(
                                                        f"UPDATE players SET osu_id = {osu_user.id} WHERE discord_id = {member.id};"
                                                    )
                                                    if ctx:
                                                        await ctx.send(
                                                            f"Pievienoja {member.mention} datubāzei ar osu! kontu {osu_user.username} (id: {osu_user.id})",
                                                            allowed_mentions=discord.AllowedMentions(
                                                                users=False
                                                            ),
                                                        )
                                                    await refresh_user_rank(
                                                        member, self.bot
                                                    )
                                                    continue
                                                # check if discord multiaccounter
                                                if member.id != result[0][0]:
                                                    await db.execute(
                                                        f"UPDATE players SET osu_id = {osu_user.id} WHERE discord_id = {member.id};"
                                                    )
                                                    await db.execute(
                                                        f"UPDATE players SET osu_id = NULL WHERE discord_id = {result[0][0]};"
                                                    )
                                                    if ctx:
                                                        await ctx.send(
                                                            f"Lietotājs {member.mention} spēlē uz osu! konta (id: {osu_user.id}), kas linkots ar <@{result[0][0]}>. Vecais konts unlinkots un linkots jaunais."
                                                        )
                                                    await refresh_user_rank(
                                                        member, self.bot
                                                    )

                                            else:
                                                if (
                                                    member.get_role(IMMIGRANT_ROLE_ID)
                                                    is None
                                                ):
                                                    role = get(
                                                        self.bot.lvguild.roles,
                                                        id=IMMIGRANT_ROLE_ID,
                                                    )
                                                    if role is None:
                                                        raise ValueError(
                                                            f"Role {IMMIGRANT_ROLE_ID} not found in guild"
                                                        )
                                                    await member.add_roles(role)
                                                    if ctx:
                                                        await ctx.send(
                                                            f"Lietotājs {member.mention} nav no Latvijas! (Pievienots imigranta role)"
                                                        )

                                        else:
                                            logger.info(
                                                f"{member.mention} jau eksistē datubāzē"
                                            )

                                            # check if osu multiaccount (datbase osu_id != activity osu_id)
                                            # logger.info(result[0][1])
                                            if osu_user.id != result[0][1]:
                                                if (
                                                    osu_user.id,
                                                    result[0][1],
                                                ) not in self.already_sent_messages:
                                                    if ctx:
                                                        await ctx.send(
                                                            f"Lietotājs {member.mention} jau eksistē ar osu! id {result[0][1]}, bet pašlaik spēlē uz cita osu! konta ar id = {osu_user.id} username = {osu_user.username}."
                                                        )
                                                    self.already_sent_messages.append(
                                                        (osu_user.id, result[0][1])
                                                    )
                                                else:
                                                    continue

                                except Exception:
                                    # Catch any unexpected errors and continue to next activity
                                    logger.exception("error in link_acc")
                                    continue
            logger.info("link acc finished")
            if POST_REQUEST_URL and POST_REQUEST_TOKEN:
                try:
                    async with self.bot.db.pool.acquire() as db:
                        result = await db.fetch(
                            "SELECT discord_id, osu_id FROM players WHERE osu_id IS NOT NULL;"
                        )
                        result_json = [
                            {"discord_id": str(r[0]), "osu_id": str(r[1])}
                            for r in result
                        ]
                        resp = await self.bot.session.post(
                            POST_REQUEST_URL,
                            json={"users": result_json},
                            headers={"Authorization": POST_REQUEST_TOKEN},
                        )
                        if resp.status == 201:
                            logger.info(
                                f"{resp.status}: posted {len(result)} users to post_request_url"
                            )
                        else:
                            logger.error(
                                f"{resp.status}: failed to post {len(result)} users to post_request_url"
                            )
                except Exception:
                    logger.exception("error in posting users to post_request_url")

        except Exception as e:
            logger.exception("error in link_acc")
            if ctx and isinstance(ctx, discord.TextChannel):
                await ctx.send(f"{repr(e)} in link_acc")

    @link_acc.before_loop
    async def before_link_acc(self) -> None:
        await self.bot.wait_until_ready()
        await wait_for_on_ready(self.bot)


async def setup(bot: OsuBot) -> None:
    await bot.add_cog(LinkUser(bot))
