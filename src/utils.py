from config import ROLE_TRESHOLDS, BOTSPAM_CHANNEL_ID, ROLES
import discord
from discord.ext import commands
from loguru import logger
from app import OsuBot
from ossapi import GameMode, UserLookupKey
from ossapi.models import User
import asyncio

# Admin role ID that can use admin commands
ADMIN_ROLE_ID = 141542368972111872


async def wait_for_on_ready(bot: OsuBot) -> None:
    """Wait for bot's on_ready to finish"""
    while not getattr(bot, "_on_ready_finished", False):
        await asyncio.sleep(0.1)


async def admin_or_role_check(interaction: discord.Interaction) -> bool:
    """Check if user is administrator or has admin role"""
    if not interaction.guild:
        return False

    # Get member - interaction.user should be a Member in guild context
    # but we'll get it from guild to be safe
    member = interaction.guild.get_member(interaction.user.id)
    if not member:
        return False

    # Check administrator permission
    if member.guild_permissions.administrator:
        return True

    # Check for admin role
    if any(role.id == ADMIN_ROLE_ID for role in member.roles):
        return True

    return False


class BaseCog(commands.Cog):
    """Base cog class with shared error handler for app commands"""

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        """Handle errors for app commands"""
        if isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.send_message(
                "You don't have permission to use this command. Administrator permission or admin role required.",
                ephemeral=True,
            )
        else:
            logger.exception(f"Error in app command: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"An error occurred: {str(error)}", ephemeral=True
                )


# seperate function to check just one user and update their role on the server
async def refresh_user_rank(member: discord.Member, bot: OsuBot) -> None:
    async with bot.db.pool.acquire() as db:
        query = await db.fetch(
            f"SELECT discord_id, osu_id FROM players WHERE osu_id IS NOT NULL AND discord_id = {member.id};"
        )
        if query != []:
            osu_user = await bot.osuapi.user(
                query[0][1], mode=GameMode.OSU, key=UserLookupKey.ID
            )
            new_role = await get_role_with_rank(
                getattr(osu_user.statistics, "country_rank", 99999)
            )
            current_role = [
                role.id for role in member.roles if role.id in ROLES.values()
            ]
            if current_role == []:
                await change_role(
                    bot=bot, discord_id=member.id, new_role_id=ROLES[new_role]
                )
            else:
                await change_role(
                    bot=bot,
                    discord_id=member.id,
                    new_role_id=ROLES[new_role],
                    current_role_id=current_role[0],
                )
            await send_rolechange_msg(
                bot=bot,
                discord_id=member.id,
                notikums="no_previous_role",
                role=new_role,
                osu_user=osu_user,
            )
            logger.info(f"refreshed rank for user {member.display_name}")


async def get_role_with_rank(rank: int) -> str:
    for role, threshold in ROLE_TRESHOLDS.items():
        if rank <= threshold:
            return role
    return "LVinf"


async def change_role(
    bot: OsuBot, discord_id: int, new_role_id: int, current_role_id: int = 0
) -> None:
    member = discord.utils.get(bot.lvguild.members, id=discord_id)
    if member is None:
        raise ValueError(f"Member {discord_id} not found in guild")
    if current_role_id != 0:
        current_role = discord.utils.get(bot.lvguild.roles, id=current_role_id)
        if current_role is None:
            raise ValueError(f"Role {current_role_id} not found in guild")
        await member.remove_roles(current_role)
    new_role = discord.utils.get(bot.lvguild.roles, id=new_role_id)
    if new_role is None:
        raise ValueError(f"Role {new_role_id} not found in guild")
    await member.add_roles(new_role)


async def update_users_in_database(bot: OsuBot) -> list[discord.Member]:
    """Update users in database by adding any guild members that aren't already in the database.

    Returns:
        list[discord.Member]: List of members that were added to the database
    """
    async with bot.db.pool.acquire() as db:
        result = await db.fetch("SELECT discord_id FROM players;")
        db_id_list = [x[0] for x in result]
        added_members: list[discord.Member] = []

        for member in bot.lvguild.members:
            if member.id not in db_id_list:
                await db.execute(
                    f"INSERT INTO players (discord_id) VALUES ({member.id});"
                )
                logger.warning(
                    f"update_user: User {member.name} (ID: {member.id}) was not in database and has been added"
                )
                added_members.append(member)

        if added_members:
            logger.info(f"update_user: Added {len(added_members)} user(s) to database")
        else:
            logger.info("update_user: No new users to add to database")

        return added_members


async def send_rolechange_msg(
    bot: OsuBot,
    notikums: str,
    discord_id: int,
    role: str | None = None,
    osu_id: int | None = None,
    osu_user: User | None = None,
) -> None:
    channel = bot.get_channel(BOTSPAM_CHANNEL_ID)
    # member = discord.utils.get(bot.lvguild.members, id=discord_id)

    # Helper function to get role name
    def get_role_name(role_key: str) -> str:
        role_obj = discord.utils.get(bot.lvguild.roles, id=ROLES[role_key])
        return role_obj.name if role_obj else role_key

    match notikums:
        case "no_previous_role":
            if role is None:
                raise ValueError("role is required for no_previous_role")
            desc = f"ir grupā **{get_role_name(role)}**!"
            embed_color = 0x14D121
        case "pacelas":
            if role is None:
                raise ValueError("role is required for pacelas")
            desc = f"pakāpās uz grupu **{get_role_name(role)}**!"
            embed_color = 0x14D121
        case "nokritas":
            if role is None:
                raise ValueError("role is required for nokritas")
            desc = f"nokritās uz grupu **{get_role_name(role)}**!"
            embed_color = 0xC41009
        case "restricted":
            desc = "ir kļuvis restricted!"
            embed_color = 0x7B5C00
        case "inactive":
            desc = "ir kļuvis inactive!"
            embed_color = 0x696969
        case "unrestricted":
            desc = "ir kļuvis unrestrictots!"
            embed_color = 0x14D121
        case _:
            # This should never happen, but pyright needs this to know desc and embed_color are always set
            raise ValueError(f"Unknown notikums: {notikums}")

    embed = discord.Embed(description=desc, color=embed_color)

    if osu_user is None:
        if osu_id is None:
            raise ValueError("osu_id is required when osu_user is None")
        osu_user = await bot.osuapi.user(
            osu_id, mode=GameMode.OSU, key=UserLookupKey.ID
        )

    embed.set_author(
        name=osu_user.username,
        url=f"https://osu.ppy.sh/users/{osu_user.id}",
        icon_url=osu_user.avatar_url,
    )

    if not channel or not isinstance(channel, discord.TextChannel):
        raise ValueError(
            f"Channel {BOTSPAM_CHANNEL_ID} not found or is not a text channel"
        )
    await channel.send(embed=embed)
