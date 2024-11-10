import discord
from discord.ext import commands, tasks
from discord.utils import get

from config import *

class RolesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.refresh_roles.start()

    def cog_unload(self):
        self.refresh_roles.cancel()

    async def get_role_with_rank(self, rank):
        match rank:
            case 1:
                return 'LV1'
            case rank if rank in range(2,6):
                return 'LV5'
            case rank if rank in range(6,11):
                return 'LV10'
            case rank if rank in range(11,26):
                return 'LV25'
            case rank if rank in range(26,51):
                return 'LV50'
            case rank if rank in range(51,101):
                return 'LV100'
            case rank if rank in range(101,251):
                return 'LV250'
            case rank if rank in range(251,501):
                return 'LV500'
            case rank if rank in range(501,1001):
                return 'LV1000'
            case rank if rank > 1000:
                return 'LVinf'

    async def change_role(self, discord_id, new_role_id, current_role_id=0):
        member = get(self.bot.lvguild.members, id=discord_id)
        if current_role_id != 0:
            await member.remove_roles(get(self.bot.lvguild.roles, id=current_role_id))
        await member.add_roles(get(self.bot.lvguild.roles, id=new_role_id))

    async def send_rolechange_msg(self, notikums, discord_id, role=0, osu_id=None, osu_user=None):
        channel = self.bot.get_channel(BOTSPAM_CHANNEL_ID)
        member = get(self.bot.lvguild.members, id=discord_id)

        match notikums:
            case 'no_previous_role':
                desc = f"ir grupā **{get(self.bot.lvguild.roles, id=self.roles[role]).name}**!"
                embed_color=0x14d121
            case 'pacelas':
                desc = f"pakāpās uz grupu **{get(self.bot.lvguild.roles, id=self.roles[role]).name}**!"
                embed_color=0x14d121
            case 'nokritas':
                desc = f"nokritās uz grupu **{get(self.bot.lvguild.roles, id=self.roles[role]).name}**!"
                embed_color=0xc41009
            case 'restricted':
                desc = "ir kļuvis restricted!"
                embed_color=0x7b5c00
            case 'inactive':
                desc = "ir kļuvis inactive!"
                embed_color=0x696969
            case 'unrestricted':
                desc = "ir kļuvis unrestrictots!"
                embed_color=0x14d121

        embed = discord.Embed(description=desc, color=embed_color)

        if osu_user == None:
            osu_user = await self.bot.osuapi.get_user(name=osu_id, mode='osu', key='id')

        embed.set_author(
            name=osu_user['username'],
            url=f"https://osu.ppy.sh/users/{osu_user['id']}",
            icon_url=osu_user['avatar_url']
        )

        await channel.send(embed=embed)

    @tasks.loop(minutes=15)
    async def refresh_roles(self):
        try:
            ctx = self.bot.get_channel(BOT_CHANNEL_ID)
            async with self.bot.pool.acquire() as db:
                cursor = ''
                ranking = []
                #get the first 1000 players from LV country leaderboard
                for i in range(20):
                    response = await self.bot.osuapi.get_rankings(mode='osu', type='performance', country='LV', cursor=cursor)
                    cursor = response['cursor']['page']
                    ranking.extend(response['ranking'])

                ranking_id_list = [x['user']['id'] for x in ranking]

                result = await db.fetch(f'SELECT discord_id, osu_id FROM players WHERE osu_id IS NOT NULL;')
                member_id_list = [x.id for x in self.bot.lvguild.members]

                for row in result:
                    if row[0] not in member_id_list:
                        continue
                    try:
                        country_rank = ranking_id_list.index(row[1]) + 1
                    except ValueError:
                        country_rank = 99999

                    current_role = [self.rev_roles[role.id] for role in get(self.bot.lvguild.members, id=row[0]).roles if role.id in self.roles.values()]

                    if country_rank == 99999:
                        osu_user = await self.bot.osuapi.get_user(name=row[1], mode='osu', key='id')
                        if osu_user == {'error': None}:
                            osu_api_check = await self.bot.osuapi.get_user(name=2, mode='osu', key='id')
                            if osu_api_check == {'error': None}:
                                continue
                            if current_role == []:
                                await self.change_role(discord_id = row[0], new_role_id=self.roles['restricted'])
                                await self.send_rolechange_msg(discord_id=row[0], notikums='restricted', osu_user=osu_user)
                                continue
                            if self.roles[current_role[0]] != self.roles['restricted']:
                                await self.change_role(discord_id = row[0], current_role_id=self.roles[current_role[0]], new_role_id=self.roles['restricted'])
                                await self.send_rolechange_msg(discord_id=row[0], notikums='restricted', osu_user=osu_user)
                            continue

                        if osu_user['statistics']['is_ranked'] == False:
                            if current_role == []:
                                await self.change_role(discord_id = row[0], new_role_id=self.roles['inactive'])
                                await self.send_rolechange_msg(discord_id=row[0], notikums='inactive', osu_user=osu_user)
                                continue
                            if self.roles[current_role[0]] != self.roles['inactive']:
                                await self.change_role(discord_id = row[0], current_role_id=self.roles[current_role[0]], new_role_id=self.roles['inactive'])
                                await self.send_rolechange_msg(discord_id=row[0], notikums='inactive', osu_user=osu_user)
                            continue

                    new_role = await self.get_role_with_rank(country_rank)

                    if current_role == []:
                        await self.change_role(discord_id=row[0], new_role_id=self.roles[new_role])
                        await self.send_rolechange_msg(discord_id=row[0], notikums='no_previous_role', role=new_role, osu_id=row[1])

                    elif current_role[0] == 'restricted':
                        await self.change_role(discord_id=row[0], current_role_id=self.roles[current_role[0]], new_role_id=self.roles[new_role])
                        await self.send_rolechange_msg(discord_id=row[0], notikums='unrestricted', role=new_role, osu_id=row[1])
                   
                    elif new_role != current_role[0]:
                        if self.rolesvalue[new_role] < self.rolesvalue[current_role[0]]:
                            await self.change_role(discord_id=row[0], current_role_id=self.roles[current_role[0]], new_role_id=self.roles[new_role])
                            await self.send_rolechange_msg(discord_id=row[0], notikums='pacelas', role=new_role, osu_id=row[1])
                            continue
                        if self.rolesvalue[new_role] > self.rolesvalue[current_role[0]]:
                            await self.change_role(discord_id=row[0], current_role_id=self.roles[current_role[0]], new_role_id=self.roles[new_role])
                            await self.send_rolechange_msg(discord_id=row[0], notikums='nokritas', role=new_role, osu_id=row[1])
                            continue

            print("roles refreshed")
        except Exception as e:
            print(repr(e))

    async def refresh_user_rank(self, member):
        async with self.bot.pool.acquire() as db: 
            query = await db.fetch(f'SELECT discord_id, osu_id FROM players WHERE osu_id IS NOT NULL AND discord_id = {member.id};')
            if query != []:
                osu_user = await self.bot.osuapi.get_user(name=query[0][1], mode='osu', key='id')
                new_role = await self.get_role_with_rank(osu_user["statistics"]["country_rank"])
                current_role = [role.id for role in member.roles if role.id in self.roles.values()]
                if current_role == []:
                    await self.change_role(discord_id=member.id, new_role_id=self.roles[new_role])
                else:
                    await self.change_role(discord_id=member.id, new_role_id=self.roles[new_role], current_role_id=current_role)
                await self.send_rolechange_msg(discord_id=member.id, notikums='no_previous_role', role=new_role, osu_user=osu_user)
                print(f"refreshed rank for user {member.display_name}")

async def setup(bot):
    await bot.add_cog(RolesCog(bot)) 