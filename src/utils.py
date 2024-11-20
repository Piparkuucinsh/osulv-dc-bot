from config import MODS_DICT, ROLE_TRESHOLDS, BOTSPAM_CHANNEL_ID, ROLES
import discord
from loguru import logger
from app import OsuBot


async def mods_int_from_list(mods):
    modint = 0
    for mod in mods:
        modint += MODS_DICT[mod]
    return int(modint)


# seperate function to check just one user and update their role on the server
async def refresh_user_rank(member, bot: OsuBot):
    async with bot.db.pool.acquire() as db:
        query = await db.fetch(
            f"SELECT discord_id, osu_id FROM players WHERE osu_id IS NOT NULL AND discord_id = {member.id};"
        )
        if query != []:
            osu_user = await bot.osuapi.get_user(name=query[0][1], mode="osu", key="id")
            new_role = await get_role_with_rank(osu_user["statistics"]["country_rank"])
            [current_role] = [
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
                    current_role_id=current_role,
                )
            await send_rolechange_msg(
                bot=bot,
                discord_id=member.id,
                notikums="no_previous_role",
                role=new_role,
                osu_user=osu_user,
            )
            logger.info(f"refreshed rank for user {member.display_name}")


async def get_role_with_rank(rank):
    for role, threshold in ROLE_TRESHOLDS.items():
        if rank <= threshold:
            return role
    return "LVinf"


async def change_role(bot, discord_id, new_role_id, current_role_id=0):
    member = discord.utils.get(bot.lvguild.members, id=discord_id)
    if current_role_id != 0:
        await member.remove_roles(
            discord.utils.get(bot.lvguild.roles, id=current_role_id)
        )
    await member.add_roles(discord.utils.get(bot.lvguild.roles, id=new_role_id))


async def send_rolechange_msg(
    bot, notikums, discord_id, role=None, osu_id=None, osu_user=None
):
    channel = bot.get_channel(BOTSPAM_CHANNEL_ID)
    # member = discord.utils.get(bot.lvguild.members, id=discord_id)

    match notikums:
        case "no_previous_role":
            if role is None:
                raise ValueError("role is required for no_previous_role")
            desc = f"ir grupā **{discord.utils.get(bot.lvguild.roles, id=ROLES[role]).name}**!"
            embed_color = 0x14D121
        case "pacelas":
            if role is None:
                raise ValueError("role is required for pacelas")
            desc = f"pakāpās uz grupu **{discord.utils.get(bot.lvguild.roles, id=ROLES[role]).name}**!"
            embed_color = 0x14D121
        case "nokritas":
            if role is None:
                raise ValueError("role is required for nokritas")
            desc = f"nokritās uz grupu **{discord.utils.get(bot.lvguild.roles, id=ROLES[role]).name}**!"
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

    embed = discord.Embed(description=desc, color=embed_color)

    if osu_user is None:
        osu_user = await bot.osuapi.get_user(name=osu_id, mode="osu", key="id")

    embed.set_author(
        name=osu_user["username"],
        url=f"https://osu.ppy.sh/users/{osu_user['id']}",
        icon_url=osu_user["avatar_url"],
    )

    await channel.send(embed=embed)
