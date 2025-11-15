import discord
from discord.ext import commands

from app import OsuBot


class Events(commands.Cog):
    # Constants at class level
    NOTIFICATIONS_CHANNEL_ID = 1148984358561136670

    def __init__(self, bot: OsuBot) -> None:
        self.bot = bot

    async def _send_notification(
        self, message: str, mention_users: bool = False
    ) -> None:
        """Helper method to send notifications to the designated channel"""
        channel = self.bot.get_channel(self.NOTIFICATIONS_CHANNEL_ID)
        if not channel or not isinstance(channel, discord.TextChannel):
            raise ValueError(
                f"Channel {self.NOTIFICATIONS_CHANNEL_ID} not found or is not a text channel"
            )

        allowed_mentions = discord.AllowedMentions(users=mention_users)
        await channel.send(message, allowed_mentions=allowed_mentions)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        result = await self.bot.db.get_user(member.id)
        message = (
            f"{member.mention} pievienojās serverim!"
            if not result
            else f"{member.mention} atkal pievienojās serverim!"
        )

        if not result:
            await self.bot.db.create_user(member.id)

        await self._send_notification(message)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self._send_notification(f"**{member.display_name}** izgāja no servera!")
        await self._send_notification("https://tenor.com/view/rip-bozo-gif-22294771")

    @commands.Cog.listener()
    async def on_member_ban(
        self, guild: discord.Guild, member: discord.Member | discord.User
    ) -> None:
        await self._send_notification(
            f"**{member.display_name}** ir ticis nobanots no servera!"
        )

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        await self._send_notification(
            f"**{user.display_name}** ir unbanots no servera!"
        )


async def setup(bot: OsuBot) -> None:
    await bot.add_cog(Events(bot))
