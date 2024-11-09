import discord
from discord.ext import commands
from discord.utils import get
import logging

from config import *

class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def delete(self, ctx):
        if not ctx.author.guild_permissions.manage_messages:
            await ctx.send("You don't have permission to use this command.")
            return

        channel = self.bot.get_channel(BOTSPAM_CHANNEL_ID)
        if not channel:
            await ctx.send("Target channel not found.")
            return

        deleted = 0
        async for message in channel.history(limit=20):
            if message.author.id == BOT_SELF_ID:
                try:
                    await message.delete()
                    deleted += 1
                except discord.Forbidden:
                    await ctx.send("Bot lacks permission to delete messages.")
                    return
                except discord.NotFound:
                    continue
        
        await ctx.send(f"Deleted {deleted} messages.")

    @commands.command()
    async def check(self, ctx, arg):
        if ctx.channel.id != BOT_CHANNEL_ID:
            return
        
        await ctx.send(arg)

    @commands.command()
    async def desa(self, ctx):
        await ctx.send('<:desa:272418900111785985>')


    @commands.command()
    async def pervert(self, ctx):
        try:
            role = get(self.bot.lvguild.roles, id=PERVERT_ROLE)
            if not role:
                await ctx.send("Role not found.")
                return
                
            await ctx.author.add_roles(role)
            await ctx.send(f"Added role to {ctx.author.display_name}")
        except discord.Forbidden:
            await ctx.send("Bot lacks permission to manage roles.")
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            channel = self.bot.get_channel(BOT_CHANNEL_ID)
            await channel.send(f"An error occurred: {str(e)}")
            

async def setup(bot):
    await bot.add_cog(Commands(bot)) 