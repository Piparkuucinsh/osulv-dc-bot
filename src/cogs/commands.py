import discord
from discord.utils import get
from loguru import logger
from app import OsuBot

from config import (
    BOT_CHANNEL_ID,
    BOTSPAM_CHANNEL_ID,
    PERVERT_ROLE,
    BOT_SELF_ID,
    ROLES,
    SERVER_ID,
)
from utils import admin_or_role_check, BaseCog, update_users_in_database
from .roles import RolesCog


class Commands(BaseCog):
    def __init__(self, bot: OsuBot) -> None:
        self.bot: OsuBot = bot

    @discord.app_commands.command(
        name="delete", description="Delete bot messages from botspam channel"
    )
    @discord.app_commands.describe(limit="Number of messages to check (default: 20)")
    @discord.app_commands.check(admin_or_role_check)
    async def delete(self, interaction: discord.Interaction, limit: int = 20) -> None:
        channel = self.bot.get_channel(BOTSPAM_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message(
                "Target channel not found.", ephemeral=True
            )
            return

        await interaction.response.defer()
        deleted = 0
        async for message in channel.history(limit=limit):  # type: ignore
            if message.author.id == BOT_SELF_ID:
                try:
                    await message.delete()
                    deleted += 1
                except discord.Forbidden:
                    await interaction.followup.send(
                        "Bot lacks permission to delete messages.", ephemeral=True
                    )
                    return
                except discord.NotFound:
                    continue

        await interaction.followup.send(f"Deleted {deleted} messages.")

    @discord.app_commands.command(
        name="check", description="Echo a message (bot channel only)"
    )
    @discord.app_commands.describe(message="The message to echo")
    @discord.app_commands.check(admin_or_role_check)
    async def check(self, interaction: discord.Interaction, message: str) -> None:
        if interaction.channel and interaction.channel.id != BOT_CHANNEL_ID:
            await interaction.response.send_message(
                "This command can only be used in the bot channel.", ephemeral=True
            )
            return

        await interaction.response.send_message(message)

    @discord.app_commands.command(name="desa", description="Send desa emoji")
    async def desa(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("<:desa:272418900111785985>")

    @discord.app_commands.command(
        name="pervert", description="Add pervert role to yourself"
    )
    async def pervert(self, interaction: discord.Interaction) -> None:
        try:
            if not interaction.guild:
                await interaction.response.send_message(
                    "This command can only be used in a server.", ephemeral=True
                )
                return

            role = get(self.bot.lvguild.roles, id=PERVERT_ROLE)
            if not role:
                await interaction.response.send_message(
                    "Role not found.", ephemeral=True
                )
                return

            # Get member from guild to ensure we have a Member object
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                await interaction.response.send_message(
                    "Could not find member in guild.", ephemeral=True
                )
                return

            await member.add_roles(role)
            await interaction.response.send_message(
                f"Added role to {member.display_name}"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Bot lacks permission to manage roles.", ephemeral=True
            )
        except Exception as e:
            logger.exception("An error occurred in pervert command")
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"An error occurred: {str(e)}", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"An error occurred: {str(e)}", ephemeral=True
                )



    @discord.app_commands.command(
        name="update_user", description="Update users in database (bot channel only)"
    )
    @discord.app_commands.check(admin_or_role_check)
    async def update_user(self, interaction: discord.Interaction) -> None:
        if interaction.channel and interaction.channel.id != BOT_CHANNEL_ID:
            await interaction.response.send_message(
                "This command can only be used in the bot channel.", ephemeral=True
            )
            return

        await interaction.response.defer()

        # Run the update and get added users
        added_members = await update_users_in_database(self.bot)

        if added_members:
            users = "Pievienoja "
            for member in added_members:
                users += f"{member.name}, "
            await interaction.followup.send(f"{users.removesuffix(', ')} datubāzei.")
        else:
            await interaction.followup.send("Nevienu nepievienoja datubāzei.")

    @discord.app_commands.command(
        name="purge_roles",
        description="Purge discord roles from players that aren't linked in the database",
    )
    @discord.app_commands.check(admin_or_role_check)
    async def purge_roles(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        async with self.bot.db.pool.acquire() as db:
            result = await db.fetch(
                "SELECT discord_id FROM players WHERE osu_id IS NOT NULL;"
            )
            db_id_list = [x[0] for x in result]
            purged_count = 0
            for member in self.bot.lvguild.members:
                if member.id not in db_id_list:
                    current_role_id = [
                        role.id for role in member.roles if role.id in ROLES.values()
                    ]
                    if current_role_id != []:
                        role = get(self.bot.lvguild.roles, id=current_role_id[0])
                        if role:
                            await member.remove_roles(role)
                            purged_count += 1

            await interaction.followup.send(
                f"Purged roles for {purged_count} member(s)."
            )

    @discord.app_commands.command(
        name="refresh", description="Refresh roles manually"
    )
    @discord.app_commands.check(admin_or_role_check)
    async def refresh(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        roles_cog = self.bot.get_cog('RolesCog')
        if roles_cog is not None:
            await roles_cog.refresh_roles()  # type: ignore
            await interaction.followup.send("Roles refreshed successfully.")
        else:
            await interaction.followup.send("RolesCog not found.", ephemeral=True)



async def setup(bot: OsuBot) -> None:
    await bot.add_cog(Commands(bot), guild=discord.Object(id=SERVER_ID))
