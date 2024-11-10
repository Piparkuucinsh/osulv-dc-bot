import discord
from discord.ext import commands
from osu_api import OsuApiV2
import asyncpg

from config import *

class OsuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = True

        self.osuapi = OsuApiV2()
        self.pool = None
        
        super().__init__(command_prefix='!', intents=intents)
        
    async def setup_hook(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL, ssl='require')
        
        await self.load_extension('cogs.events')
        await self.load_extension('cogs.commands')
        await self.load_extension('cogs.link_user')
        await self.load_extension('cogs.roles')
        await self.load_extension('cogs.user_newbest')

        

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        print('Servers connected to:')
        for guild in self.guilds:
            print(guild.name)

def main():
    bot = OsuBot()
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()