import discord
from discord.ext import commands, tasks
from discord.utils import get
from loguru import logger

from utils import refresh_user_rank

from config import BOT_CHANNEL_ID, SERVER_ID

OSU_APPLICATION_ID = 367827983903490050
IMMIGRANT_ROLE_ID = 539951111382237198

class LinkUser(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.already_sent_messages = []
        self.link_acc.start()

    def cog_unload(self):
        self.link_acc.cancel()

    @tasks.loop(minutes=5)
    async def link_acc(self):
        try:
            ctx = self.bot.get_channel(BOT_CHANNEL_ID)
            async with self.bot.db.pool.acquire() as db:
                for guild in self.bot.guilds:
                    for member in guild.members:
                        if member.activities is not None:
                            for osu_activity in member.activities:
                                try:
                                    if osu_activity.application_id == OSU_APPLICATION_ID:         
                                        username = osu_activity.large_image_text.split('(', 1)[0].removesuffix(' ')
                                        if username == osu_activity.large_image_text:
                                            continue
                                            
                                        osu_user = await self.bot.osuapi.get_user(name=username, mode='osu', key='username')
                                        
                                        if osu_user == {'error': None}:
                                            continue

                                        queryString = f'SELECT discord_id, osu_id FROM players WHERE discord_id = {member.id} AND osu_id IS NOT NULL'

                                        result = await db.fetch(queryString)
                                        if result == []:
                                            in_db_check = await db.fetch(f'SELECT discord_id FROM players WHERE discord_id = {member.id}')
                                            if in_db_check == []:
                                                logger.warning(f'link_user: discord member {member.id} not in db')
                                                continue

                                            if osu_user['country_code'] == 'LV':
                                                result = await db.fetch(f'SELECT discord_id, osu_id FROM players WHERE osu_id = {osu_user["id"]};')
                                                if result == []:
                                                    await db.execute(f'UPDATE players SET osu_id = {osu_user["id"]} WHERE discord_id = {member.id};')
                                                    await ctx.send(f'Pievienoja {member.mention} datubāzei ar osu! kontu {osu_user["username"]} (id: {osu_user["id"]})', allowed_mentions = discord.AllowedMentions(users = False))
                                                    await refresh_user_rank(member, self.bot)
                                                    continue
                                                #check if discord multiaccounter
                                                if member.id != result[0][0]:
                                                    await db.execute(f'UPDATE players SET osu_id = {osu_user["id"]} WHERE discord_id = {member.id};')
                                                    await db.execute(f'UPDATE players SET osu_id = NULL WHERE discord_id = {result[0][0]};')
                                                    await ctx.send(f'Lietotājs {member.mention} spēlē uz osu! konta (id: {osu_user["id"]}), kas linkots ar <@{result[0][0]}>. Vecais konts unlinkots un linkots jaunais.')
                                                    await refresh_user_rank(member, self.bot)

                                            else:
                                                if member.get_role(IMMIGRANT_ROLE_ID) is None:
                                                    await member.add_roles(get(self.bot.lvguild.roles, id=IMMIGRANT_ROLE_ID))
                                                    await ctx.send(f'Lietotājs {member.mention} nav no Latvijas! (Pievienots imigranta role)')
                                        
                                        else:
                                            logger.info(f"{member.mention} jau eksistē datubāzē")

                                            #check if osu multiaccount (datbase osu_id != activity osu_id)
                                            print(result[0][1])
                                            if osu_user['id'] != result[0][1]:
                                                if (osu_user['id'], result[0][1]) not in self.already_sent_messages:
                                                    await ctx.send(f'Lietotājs {member.mention} jau eksistē ar osu! id {result[0][1]}, bet pašlaik spēlē uz cita osu! konta ar id = {osu_user["id"]}.')
                                                    self.already_sent_messages.append((osu_user['id'], result[0][1]))
                                                else:
                                                    continue

                                except AttributeError as ae:
                                    if str(ae) == "'CustomActivity' object has no attribute 'application_id'" or "'Spotify' object has no attribute 'application_id'" or "'Game' object has no attribute 'application_id'" or "'Streaming' object has no attribute 'application_id'":
                                        continue
                                    else:
                                        raise ae
                                except KeyError as ke:
                                    if str(ke) == "'large_image_text'":
                                        continue
                                    else:
                                        raise ke            
            logger.info('link acc finished')

        except Exception as e:
            logger.error(repr(e))
            await ctx.send(f'{repr(e)} in link_acc')

    @link_acc.before_loop
    async def before_link_acc(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(LinkUser(bot)) 