import os
import discord
from discord.ext import commands, tasks
from discord.utils import get
from dotenv import load_dotenv, set_key
import aiosqlite
import aiohttp
import json


load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
API_CLIENT_ID = os.getenv('API_CLIENT_ID') #osu api client id
API_CLIENT_SECRET = os.getenv('API_CLIENT_SECRET') #osu api client secret
SERVER_ID = int(os.getenv('SERVER_ID'))
OSU_API_TOKEN = os.getenv('OSU_API_TOKEN')
BOT_CHANNEL_ID = int(os.getenv('BOT_CHANNEL_ID'))
db_file = 'users.db'




roles = {
    'LV1': 202057149860282378,
    'LV5': 202061474213003265,
    'LV10': 202061507037495296,
    'LV25': 202061546787045377,
    'LV50': 202061582006485002,
    'LV100': 202061613644251136,
    'LV250': 297854952435351552,
    'LV500': 915646723588751391,
    'LV1000': 915647090581966858,
    'LVinf': 915647192755212289,
    'restricted': 348195423841943564,
    'inactive': 964604143912255509,
}

rev_roles = dict((v,k) for k,v in roles.items())

rolesvalue = dict((key,count) for count, key in enumerate(roles.keys()))

async def get_role_with_rank(rank):
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


        

#parameters = {
#            'client_id': API_CLIENT_ID,
#            'client_secret': API_CLIENT_SECRET,
#            'grant_type':'client_credentials',
#            'scope':'public'
#            }
#request = requests.post('https://osu.ppy.sh/oauth/token', data=parameters)
#print(request.content)
#with open('token.json', 'w') as outfile:
#    json.dump(r.json(), outfile)


class OsuApiV2():
    #async def __init__(self, client_id, client_secret):
    #    while True:
    #        tokenrequest = await self.refresh_token(client_id, client_secret)
    #        self.token = tokenrequest['access_token']
    #        time.sleep(tokenrequest['expires_in'] - 1000)

    token = OSU_API_TOKEN
    session = aiohttp.ClientSession()


    async def refresh_token(self, client_id, client_secret):
        parameters = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type':'client_credentials',
            'scope':'public'
            }
        async with self.session.post('https://osu.ppy.sh/oauth/token', data=parameters) as response:
            responsejson = await response.json()
            self.token = responsejson['access_token']
            set_key(key_to_set='OSU_API_TOKEN', value_to_set=self.token, dotenv_path='.env')


    async def get_user(self, name, mode, key):
            async with self.session.get(f'https://osu.ppy.sh/api/v2/users/{name}/{mode}', params={'key':key}, headers={'Authorization':f'Bearer {self.token}'}) as response:
                return await response.json()

    async def get_rankings(self, mode, type, country, cursor):
        async with self.session.get(f'https://osu.ppy.sh/api/v2/rankings/{mode}/{type}', params={'country':country, 'page':cursor}, headers={'Authorization':f'Bearer {self.token}'}) as response:
            return await response.json()

    


osuapi = OsuApiV2()
#async def huinja():
#    response = await osuapi.get_user(name=27267272, mode='osu', key='id')
#    print(response)
#    with open('osu_user.json', 'w') as outfile:
#        await json.dump(response, outfile)



intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True
bot = commands.Bot(intents=intents, command_prefix='$')

@bot.command()
async def token_reset(ctx):
    await osuapi.refresh_token(client_id=API_CLIENT_ID, client_secret=API_CLIENT_SECRET)
    await ctx.send('token reset')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
   # update_roles.start()

    print('Servers connected to:')
    for guild in bot.guilds:
        print(guild.name)

    global lvguild
    lvguild = get(bot.guilds, id=SERVER_ID)
    #await huinja()

@bot.event
async def on_member_join(member):
    guild = member.guild
    channel = get(lvguild.channels, id=266580155860779009)
    async with aiosqlite.connect(db_file) as db:
        query = await db.execute(f'SELECT * FROM players WHERE discord_id = {member.id};')
        result = query.fetchall()
        if result == []:
            await db.execute(f'INSERT INTO players (discord_id) VALUES ({member.id};')
            to_send = f'{member.mention} ir pievienojies {guild.name}!'
            await channel.send(to_send)
        else:
            to_send = f'{member.mention} ir atkal pievienojies {guild.name}!'
            await channel.send(to_send)
        await db.commit()
    

@bot.event
async def on_member_remove(member):
    guild = member.guild
    channel = get(lvguild.channels, id=266580155860779009)
    to_send = f'{member.mention} ir izgājis no {guild.name}!'
    await channel.send(to_send)



@bot.command()
async def test_query(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    async with aiosqlite.connect(db_file) as db:
        async with db.execute(f'SELECT * FROM players WHERE osu_id IS NOT NULL;') as query:
            rows = await query.fetchall()
            for row in rows:
                print(row)
            

@bot.command()
async def test_get_ranking(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    cursor = ''
    ranking = []
    for i in range(2):
            response = await osuapi.get_rankings(mode='osu', type='performance', country='LV', cursor=cursor)
            cursor = response['cursor']['page']
            ranking.extend(response['ranking'])
            print(i)
            print(response['ranking'][0]['pp'])
    with open('json_data.json', 'w') as outfile:
        json.dump(ranking, outfile)
    await ctx.send("tested gettiung rwnajibn")

@bot.command()
async def test_get_singular_ranking_page(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    cursor = ''
    response = await osuapi.get_rankings(mode='osu', type='performance', country='LV', cursor=cursor)
    with open('json_data.json', 'w') as outfile:
        json.dump(response, outfile)
    await ctx.send('crazy')

    
@bot.command()
async def test_get_restricted_user(ctx):
    osu_user = await osuapi.get_user(name=9533316, mode='osu', key='id')
    print(osu_user)


async def change_role(discord_id, new_role_id, current_role_id=0):
    member = get(lvguild.members, id=discord_id)
    if current_role_id != 0:
        await member.remove_roles(get(lvguild.roles, id=current_role_id))
    await member.add_roles(get(lvguild.roles, id=new_role_id))
    
async def send_rolechange_msg(case, discord_id, role=0):
    channel = get(lvguild.channels, id=266580155860779009)
    member = get(lvguild.members, id=discord_id)
    if case == 'no_previous_role':
        await channel.send(f'Spēlētājs {member.mention} ir grupā {role}.', allowed_mentions = discord.AllowedMentions(users = False))
    if case == 'pacelas':
        await channel.send(f'Spēlētājs {member.mention} pacēlās uz grupu {role}.', allowed_mentions = discord.AllowedMentions(users = False))
    if case == 'nokritas':
        await channel.send(f'Spēlētājs {member.mention} nokrita uz grupu {role}.', allowed_mentions = discord.AllowedMentions(users = False))
    if case == 'restricted':
        await channel.send(f'Spēlētājs {member.mention} kļuva restricted!', allowed_mentions = discord.AllowedMentions(users = False))
    if case == 'inactive':
        await channel.send(f'Spēlētājs {member.mention} ir kļuvis neaktīvs!', allowed_mentions = discord.AllowedMentions(users = False))


@bot.command()
async def test_current_role(ctx, id_arg):
    current_role = [rev_roles[role.id] for role in get(lvguild.members, id=int(id_arg)).roles if role.id in roles.values()]
    await ctx.send(f'{get(lvguild.members, id=int(id_arg)).mention} role ir {current_role[0]}', allowed_mentions = discord.AllowedMentions(users = False))

#@tasks.loop(minutes=5)
@bot.command()
async def link_acc(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    async with aiosqlite.connect(db_file) as db:
        for guild in bot.guilds:
            for member in guild.members:
                #print(member.name)
                #print(member.activity)
                if member.activities != None:
                    try:
                        for activity in member.activities:
                            if activity.application_id == 367827983903490050:
                                query = await db.execute(f'SELECT * FROM players WHERE discord_id = {member.id} AND osu_id IS NOT NULL')
                                result = await query.fetchall()
                                if result == []:
                                    #print(member.activity.application_id)
                                    #print(list(activity.assets.keys()))
                                    username = member.activity.assets['large_text'].split('(', 1)[0].removesuffix(' ')
                                    #print(username)
                                    osu_user = await osuapi.get_user(name=username, mode='osu', key='username')
                                    #print(osu_user)
                                    if osu_user['country_code'] == 'LV':
                                        query = await db.execute(f'SELECT * FROM players WHERE osu_id = {osu_user["id"]};')
                                        result = await query.fetchall()
                                        #check if discord multiaccounter
                                        if result == []:
                                            await db.execute(f'UPDATE players SET osu_id = "{osu_user["id"]}" WHERE discord_id = {member.id};')
                                            await ctx.send(f'Pievienoja {member.mention} datubāzei ar osu! kontu {osu_user["username"]} (id: {osu_user["id"]})', allowed_mentions = discord.AllowedMentions(users = False))
                                            continue
                                        if member.id != result[0][0]:
                                            await db.execute(f'UPDATE players SET osu_id = "{osu_user["id"]}" WHERE discord_id = {member.id};')
                                            await db.execute(f'UPDATE players SET osu_id = NULL WHERE discord_id = {result[0][0]};')
                                            await ctx.send(f'Lietotājs {member.mention} spēlē uz osu! konta (id: {osu_user["id"]}), kas linkots ar <@{result[0][0]}>. Vecais konts unlinkots un linkots jaunais.')

                                    else:
                                        await member.add_roles(get(lvguild.roles, id=539951111382237198))
                                        await ctx.send(f'Lietotājs {member.mention} nav no Latvijas! (Pievienots imigranta role)')

                                else:
                                    print(f"{member.mention} jau eksistē datubāzē")
                                    username = activity.assets['large_text'].split('(', 1)[0].removesuffix(' ')
                                    osu_user = await osuapi.get_user(name=username, mode='osu', key='username')
                                    #check if osu multiaccount (datbase osu_id != activity osu_id)
                                    print(result[0][1])
                                    if osu_user['id'] != result[0][1]:
                                        await ctx.send(f'Lietotājs {member.mention} jau eksistē ar osu! id {result[0][1]}, bet pašlaik spēlē uz cita osu! konta ar id = {osu_user["id"]}. <@&963906948670046248>')

                    except AttributeError as ae:
                        if str(ae) == "'CustomActivity' object has no attribute 'application_id'":
                            continue
                        if str(ae) == "'Spotify' object has no attribute 'application_id'":
                            continue
                        if str(ae) == "'Game' object has no attribute 'application_id'":
                            continue
                        if str(ae) == "'Streaming' object has no attribute 'application_id'":
                            continue
                        else:
                            raise ae
                    except KeyError as ke:
                        if str(ke) == "'large_text'":
                            continue
                        else:
                            raise ke

        await db.commit()
              
    await ctx.send(f'Kontu savienošanas operācija pabeigta.')
    
@bot.command()
async def refresh_roles(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    async with aiosqlite.connect(db_file) as db:
        cursor = ''
        ranking = []
        for i in range(20):
            response = await osuapi.get_rankings(mode='osu', type='performance', country='LV', cursor=cursor)
            cursor = response['cursor']['page']
            ranking.extend(response['ranking'])


        async with db.execute(f'SELECT * FROM players WHERE osu_id IS NOT NULL;') as query:
            result = await query.fetchall()
            member_id_list = [x.id for x in lvguild.members]
            for row in result:
                if row[0] not in member_id_list:
                    continue


                inrange = False
                for count, user in enumerate(ranking):
                    if user['user']['id'] == row[1]:
                        country_rank = count+1
                        inrange = True
                        break
                           
                if inrange == False:
                    country_rank = 99999

                current_role = [rev_roles[role.id] for role in get(lvguild.members, id=row[0]).roles if role.id in roles.values()]

                if country_rank == 99999:
                    osu_user = await osuapi.get_user(name=row[1], mode='osu', key='id')
                    if osu_user == {'error': None}:
                        print(f'user <@{row[0]}> ir restricted')
                        #set restricted role
                        if current_role == []:
                            await change_role(discord_id = row[0], new_role_id=roles['restricted'])
                            await send_rolechange_msg(discord_id=row[0], case='restricted')
                            continue
                        if roles[current_role[0]] != roles['restricted']:
                            await change_role(discord_id = row[0], current_role_id=roles[current_role[0]], new_role_id=roles['restricted'])
                            await send_rolechange_msg(discord_id=row[0], case='restricted')
                        
                        continue
                    if osu_user['statistics']['is_ranked'] == False:
                        print(f'user {osu_user["username"]} is inactive')
                        #set inactive role
                        if current_role == []:
                            await change_role(discord_id = row[0], new_role_id=roles['inactive'])
                            await send_rolechange_msg(discord_id=row[0], case='inactive')
                            continue
                        if roles[current_role[0]] != roles['inactive']:
                            await change_role(discord_id = row[0], current_role_id=roles[current_role[0]], new_role_id=roles['inactive'])
                            await send_rolechange_msg(discord_id=row[0], case='inactive')
                        
                        continue


                
                
                new_role = await get_role_with_rank(country_rank)
    


                print(f'<@{row[0]}> pasreizejais role ir {current_role}')

                if current_role == []:
                    print(f"linked cilvekam nav role serverī, vajadzetu but {new_role}")
                    #set role
                    await change_role(discord_id=row[0], new_role_id=roles[new_role])
                    await send_rolechange_msg(discord_id=row[0], case='no_previous_role', role=new_role)
                    continue
                

                if new_role != current_role[0]:
                    #user = await bot.fetch_user(row[0])
                    if rolesvalue[new_role] < rolesvalue[current_role[0]]:
                        #set role
                        await change_role(discord_id=row[0], current_role_id=roles[current_role[0]], new_role_id=roles[new_role])
                        await send_rolechange_msg(discord_id=row[0], case='pacelas', role=new_role)
                        continue
                    if rolesvalue[new_role] > rolesvalue[current_role[0]]:
                        #set role
                        await change_role(discord_id=row[0], current_role_id=roles[current_role[0]], new_role_id=roles[new_role])
                        await send_rolechange_msg(discord_id=row[0], case='nokritas', role=new_role)
                        continue
                else:
                    #user = await bot.fetch_user(row[0])
                    print(f'Lietotājam {get(lvguild.members, id=row[0]).mention} jau ir pareizais role {current_role}.')
            
        await db.commit()
    await ctx.send(f'Roles refreshed.')
    


@bot.command()
async def test_mention(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    guild = get(bot.guilds, id=119569280869072896)
    await ctx.send(f'{get(guild.members, id=240033379096068096).mention}')



@bot.command()
async def reset_db(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    print('called')
    async with aiosqlite.connect(db_file) as db:
        #guild = bot.get_guild(SERVER_ID)
        await db.execute(f'DELETE FROM players')
        for guild in bot.guilds:
            for member in guild.members:
              await db.execute(f'INSERT INTO players (discord_id) VALUES ({member.id});')
            #adding existing roles into database (may not be needed)
#            for role in member.roles:
#                if role in roles.values:
#            if any(role == roles.values for role in member.roles):
#                db.execute(f'UPDATE users SET role_id = {role}')

        await db.commit()
    
    await ctx.send(f'Database reset.')


@bot.command()
async def update_user(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    async with aiosqlite.connect(db_file) as db:
        query = await db.execute("SELECT discord_id FROM players;")
        result = await query.fetchall()
        db_id_list = [x[0] for x in result]
        users = 'Pievienoja '
        pievienots = False
        for member in lvguild.members:
            if member.id not in db_id_list:
                await db.execute(f'INSERT INTO players (discord_id) VALUES ({member.id});')
                print(f'added {member.name} to database')
                users += f'{member.name}, '
                pievienots = True
        await db.commit()
        
        if pievienots == True:
            await ctx.send(f'{users.removesuffix(", ")} datubāzei.')
        if pievienots == False:
            await ctx.send(f'Nevienu nepievienoja datubāzei.')

@bot.command()
async def db_crosscheck(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    async with aiosqlite.connect(db_file) as pipa_db:
        async with aiosqlite.connect('osulv_old_db.db') as lobster_db:
            lobster_query = await lobster_db.execute('SELECT (discord_id), (osu_id) FROM useri;')
            lobster_result = await lobster_query.fetchall()
            pipa_query = await pipa_db.execute('SELECT * FROM players;')
            pipa_result = await pipa_query.fetchall()
            pipalist = [x[0] for x in pipa_result]
            pipa_osu_list = [x[1] for x in pipa_result]
            for row in lobster_result:
                if int(row[0]) not in pipalist:
                    print(f'<@{row[0]}> nav pipa datubaze')
                if int(row[1]) not in pipa_osu_list:
                    print(f'osu id {row[1]} nav pipa datubaze')

@bot.command()
async def create_tables(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    async with aiosqlite.connect(db_file) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS players (
                                    discord_id integer,
                                    osu_id integer,
                                );""")
        await db.commit()
        await ctx.send(f'Player table created.') 

@bot.command()
async def check(ctx, arg):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    print(f'check')
    await ctx.send(arg)

@bot.command()
async def drop_column(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    async with aiosqlite.connect(db_file) as db:
        await db.execute('ALTER TABLE players DROP COLUMN role;')
        await db.commit()
        await ctx.send('dropped role column')

    
@bot.command()
async def crazy_func(ctx):
    if ctx.channel.id == BOT_CHANNEL_ID:
        await ctx.send(f'hello')

@bot.command()
async def desa(ctx):
    await ctx.send('<:desa:272418900111785985>')


@bot.command()
async def merge_db(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    async with aiosqlite.connect(db_file) as pipa_db:
        async with aiosqlite.connect('osulv_old_db.db') as lobster_db:
            lobster_query = await lobster_db.execute('SELECT (discord_id), (osu_id) FROM useri;')
            lobster_result = await lobster_query.fetchall()
            pipa_query = await pipa_db.execute('SELECT * FROM players;')
            pipa_result = await pipa_query.fetchall()
            discord_id_list = [x[0] for x in pipa_result]
            for row in lobster_result:
                if row[0] not in discord_id_list:
                    await pipa_db.execute(f'INSERT INTO players (discord_id) VALUES ({row[0]});')
                await pipa_db.execute(f'UPDATE players SET osu_id = {row[1]} WHERE discord_id = {row[0]};')
        await pipa_db.commit()

@bot.command()
async def delete_gn(ctx):
    async with aiosqlite.connect(db_file) as db:
        await db.execute('DELETE FROM players WHERE discord_id = 1')
        await db.commit()

@bot.command()
async def delete_duplicates(ctx):
    async with aiosqlite.connect(db_file) as db:
        query = await db.execute("""
            DELETE FROM players
            WHERE rowid > (
              SELECT MIN(rowid) FROM players p2  
              WHERE players.discord_id = p2.discord_id
            );""")
        result = await query.fetchall()
        for row in result:
            print(row)
        await db.commit()

bot.run(DISCORD_TOKEN)

