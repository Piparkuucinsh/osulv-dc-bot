import os
import asyncpg
import discord
from discord.ext import commands, tasks
from discord.utils import get
from dotenv import load_dotenv, set_key
import aiohttp
import asyncio
from dateutil import parser
from datetime import datetime, timedelta, timezone
from rosu_pp_py import Calculator, ScoreParams
from math import isclose
import time

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
API_CLIENT_ID = os.getenv('API_CLIENT_ID') #osu api client id
API_CLIENT_SECRET = os.getenv('API_CLIENT_SECRET') #osu api client secret
SERVER_ID = int(os.getenv('SERVER_ID'))
OSU_API_TOKEN = os.getenv('OSU_API_TOKEN')
BOT_CHANNEL_ID = int(os.getenv('BOT_CHANNEL_ID'))

DATABASE_URL = os.getenv('DATABASE_URL')


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
    'inactive': 964604143912255509
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

mods_dict = {
    'NF': 1,
    'EZ': 2,
    'TD': 4,
    'HD': 8,
    'HR': 16,
    'SD': 32,
    'DT': 64,
    'RL': 128,
    'HT': 256,
    'NC': 576, # 512, Only set along with DoubleTime. i.e: NC only gives 576
    'FL': 1024,
    'AT': 2048,
    'SO': 4096,
    'AP': 8192,    # Autopilot
    'PF': 16416 #16384, Only set along with SuddenDeath. i.e: PF only gives 16416  
}

rank_emoji = {
    'XH': '<:SSplus:995050710406283354>',
    'X': '<:SS:995050712784453747>',
    'SH': '<:Splus:995050705926762517>',
    'S': '<:S_:995050707835166761>',
    'A': '<:A_:995050698221813770>',
    'B': '<:B_:995050700147015761>',
    'C': '<:C_:995050701879267378>',
    'D': '<:D_:995050703372439633>'
}

async def mods_int_from_list(mods):
    modint = 0
    for mod in mods:
        modint += mods_dict[mod]
    return modint

user_newbest_limit = {
    'LV1': 100,
    'LV5': 80,
    'LV10': 60,
    'LV25': 50,
    'LV50': 30,
    'LV100': 20,
    'LV250': 15,
    'LV500': 10,
    'LV1000': 5,
    'LVinf': 1,
}

class OsuApiV2():

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

    async def get_scores(self, mode, osu_id, type, limit):
        async with self.session.get(f'https://osu.ppy.sh/api/v2/users/{osu_id}/scores/{type}', params={'mode': mode, 'limit': limit}, headers={'Authorization':f'Bearer {self.token}'}) as response:
            return await response.json()

    async def get_user_recent(self, osu_id):
        async with self.session.get(f'https://osu.ppy.sh/api/v2/users/{osu_id}/recent_activity', headers={'Authorization':f'Bearer {self.token}'}) as response:
            return await response.json()

    async def get_beatmap_score(self, mode, osu_id, beatmap_id, mods=''):
        async with self.session.get(f'https://osu.ppy.sh/api/v2/beatmaps/{beatmap_id}/scores/users/{osu_id}', params={'mode': mode, 'mods': mods}, headers={'Authorization':f'Bearer {self.token}'}) as response:
            return await response.json()
    


osuapi = OsuApiV2()


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True
bot = commands.Bot(intents=intents, command_prefix='!')

#@bot.command()
@tasks.loop(hours=12)
async def token_reset():
    ctx = bot.get_channel(BOT_CHANNEL_ID)
    await osuapi.refresh_token(client_id=API_CLIENT_ID, client_secret=API_CLIENT_SECRET)
    print('token reset')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

    print('Servers connected to:')
    for guild in bot.guilds:
        print(guild.name)

    global lvguild
    lvguild = bot.get_guild(SERVER_ID)

    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, ssl='require')

    token_reset.start()
    await asyncio.sleep(5)
    link_acc.start()
    refresh_roles.start()
    user_newbest_loop.start()


@bot.command()
async def start_userbest(ctx):
    try:
        await user_newbest_loop()
    except Exception as e:
        print(repr(e))
        await ctx.send(f'{repr(e)} in userbest')

@tasks.loop(minutes=60)
async def user_newbest_loop():
    async with pool.acquire() as db:
        result = await db.fetch(f'SELECT * FROM players WHERE osu_id IS NOT NULL;')
        member_id_list = [x.id for x in lvguild.members]

        for row in result:
            if row[0] not in member_id_list:
                continue

            [current_role] = [rev_roles[role.id] for role in get(lvguild.members, id=row[0]).roles if role.id in roles.values()]
            if rolesvalue[current_role] > 9:
                continue

            if row[2] == None:
                last_checked = datetime.now(tz=timezone.utc) - timedelta(minutes=60)
            else:
                last_checked = parser.parse(row[2])
            
            limit = user_newbest_limit[current_role]

            await get_user_newbest(osu_id=row[1], limit=limit, last_checked=last_checked)

            await db.execute(f"UPDATE players SET last_checked = '{datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()}' WHERE discord_id = {row[0]}")

            time.sleep(0.1)

            
                
@bot.command()
async def delete(ctx):
    channel = bot.get_channel(266580155860779009)

    async for message in channel.history(limit=20):
        if message.author.id==442370931772358666:
            await message.delete()


async def get_user_newbest(osu_id, limit, last_checked):
    user_scores = await osuapi.get_scores(osu_id=osu_id, type='best', mode='osu', limit=limit)
    for index, score in enumerate(user_scores, start=1):
        score_time = parser.parse(score['created_at'])
        osu_user = None
        if score_time > last_checked:
            if osu_user == None:
                osu_user = await osuapi.get_user(name=osu_id, mode='osu', key='id')
            await post_user_newbest(score=score, limit=limit, scoretime=score_time, score_rank=index, osu_user=osu_user)


async def post_user_newbest(score, score_rank, limit, scoretime, osu_user):
    channel = bot.get_channel(266580155860779009)
    embed_color=0x0084FF

    beatmap_id = score["beatmap"]["id"]
    if os.path.exists(f'{beatmap_id}.osu') == False:
        async with aiohttp.ClientSession() as s:
            url = f'https://osu.ppy.sh/osu/{beatmap_id}'
            async with s.get(url) as resp:
                if resp.status == 200:
                    with open(f'{beatmap_id}.osu', mode='wb') as f:
                        f.write(await resp.read())


    pp_calc = Calculator(f'{beatmap_id}.osu')
    
    calc_params = ScoreParams(
        mods = await mods_int_from_list(score['mods'])
    )
    [calc_result] = pp_calc.calculate(calc_params)
    
    time_text = str(timedelta(seconds=score['beatmap']['total_length'])).removeprefix('0:') if calc_result.clockRate == 1 else f"{str(timedelta(seconds=score['beatmap']['total_length'])).removeprefix('0:')} ({str(timedelta(seconds=round(score['beatmap']['total_length']/calc_result.clockRate))).removeprefix('0:')})"
    bpm_text = f'{score["beatmap"]["bpm"]} BPM' if calc_result.clockRate == 1 else f'{score["beatmap"]["bpm"]} -> **{round(int(score["beatmap"]["bpm"])*calc_result.clockRate)} BPM**'
    if score['mods'] != []:
        mod_text = '\t+'
        for mod in score['mods']:
            mod_text += mod
    else:
        mod_text = ''


#    desc=f'''__**{score["pp"]:.2f}**/{calc_result.pp:.2f}pp **| #{score_rank}** personal best **|** Max:{limit}__
##{osu_user["statistics"]["global_rank"]} **|** #{osu_user["statistics"]["country_rank"]} {score["user"]["country_code"]} **|** {osu_user["statistics"]["pp"]:.2f}pp
#x{score["max_combo"]}/{calc_result.maxCombo} **|** {score["rank"]} **|** {score["score"]} **|** {score["accuracy"]:.2%} **|** +{mod_text}
#[{score["beatmapset"]["artist"]} - {score["beatmapset"]["title"]} [{score["beatmap"]["version"]}]]({score["beatmap"]["url"]})
#{time_text} **|** {bpm_text} **|** ★**{calc_result.stars:.2f}**\n <t:{int(scoretime.timestamp())}:R>'''

    #desc = f'''**[{score["beatmapset"]["artist"]} - {score["beatmapset"]["title"]} [{score["beatmap"]["version"]}] [{round(calc_result.stars, 2)}]](https://osu.ppy.sh/b/{score["beatmap"]["id"]})
    #__Personal Best #{score_rank}__**'''

    desc = f'**__Personal Best #{score_rank}__**'

    embed = discord.Embed(
            description=desc,
            color=embed_color
            )

    embed.set_author(
        name=f'{score["user"]["username"]}: {round(osu_user["statistics"]["pp"], 2):,}pp (#{osu_user["statistics"]["global_rank"]:,} {score["user"]["country_code"]}{osu_user["statistics"]["country_rank"]})',
        url=f'https://osu.ppy.sh/users/{score["user"]["id"]}',
        icon_url=score["user"]["avatar_url"]
    )
    embed.set_thumbnail(url=score['beatmapset']['covers']['list'])
    embed.url = f'https://osu.ppy.sh/b/{score["beatmap"]["id"]}'
    embed.title = f'{score["beatmapset"]["artist"]} - {score["beatmapset"]["title"]} [{score["beatmap"]["version"]}] [{round(calc_result.stars, 2)}★]'
    #embed.set_footer(text=f'Limit: {limit}')

    embed.add_field(
        name = f'** {rank_emoji[score["rank"]]}{mod_text}\t{score["score"]:,}\t({round(score["accuracy"], 4):.2%}) **',
        value = f'''**{round(score["pp"], 2)}**/{round(calc_result.pp, 2)}pp [ **{score["max_combo"]}x**/{calc_result.maxCombo}x ] {{{score["statistics"]["count_300"]}/{score["statistics"]["count_100"]}/{score["statistics"]["count_50"]}/{score["statistics"]["count_miss"]}}}
        {time_text} | {bpm_text}
        <t:{int(scoretime.timestamp())}:R> | Limit: {limit}'''

    )
    #embed.add_field(
    #    name= '\u200b',
    #    value=f'<t:{int(scoretime.timestamp())}:R> | Limit: {limit}',
    #    inline=False
    #)

    await channel.send(embed=embed)
   

#@bot.event
async def on_member_join(member):
    channel = bot.get_channel(266580155860779009)
    async with pool.acquire() as db:
        result = await db.fetch(f'SELECT discord_id FROM players WHERE discord_id = {member.id};')
        if result == []:
            await db.execute(f'INSERT INTO players (discord_id) VALUES ({member.id});')
            to_send = f'{member.mention} ir pievienojies serverim!'
            await channel.send(to_send, allowed_mentions = discord.AllowedMentions(users = False))
        else:
            to_send = f'{member.mention} ir atkal pievienojies serverim!'
            await channel.send(to_send, allowed_mentions = discord.AllowedMentions(users = False))
    

@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(266580155860779009)
    to_send = f'**{member.display_name}** ir izgājis no servera!'
    await channel.send(to_send)

@bot.event
async def on_member_ban(guild, member):
    channel = bot.get_channel(266580155860779009)
    to_send = f'**{member.display_name}** ir ticis nobanots no servera!'
    await channel.send(to_send)

@bot.event
async def on_member_unban(guild, member):
    channel = bot.get_channel(266580155860779009)
    to_send = f'**{member.display_name}** ir unbanots no servera!'
    await channel.send(to_send)

async def change_role(discord_id, new_role_id, current_role_id=0):
    member = get(lvguild.members, id=discord_id)
    if current_role_id != 0:
        await member.remove_roles(get(lvguild.roles, id=current_role_id))
    await member.add_roles(get(lvguild.roles, id=new_role_id))
    
async def send_rolechange_msg(notikums, discord_id, role=0, osu_id=None, osu_user=None):
    channel = bot.get_channel(266580155860779009)

    member = get(lvguild.members, id=discord_id)
    

    match notikums:
        case 'no_previous_role':
            desc = f"ir grupā **{get(lvguild.roles, id=roles[role]).name}**!"
            embed_color=0x14d121
        case 'pacelas':
            desc = f"pakāpās uz grupu **{get(lvguild.roles, id=roles[role]).name}**!"
            embed_color=0x14d121
        case 'nokritas':
            desc = f"nokritās uz grupu **{get(lvguild.roles, id=roles[role]).name}**!"
            embed_color=0xc41009
        case 'restricted':
            desc = "ir kļuvis restricted!"
            embed_color=0x7b5c00
            embed = discord.Embed(
                    description=desc,
                    color=embed_color)
            embed.set_author(name=member.display_name, 
                            icon_url=member.display_avatar.url)
            await channel.send(embed=embed)
            return

        case 'inactive':
            desc = "ir kļuvis inactive!"
            embed_color=0x696969
        case 'unrestricted':
            desc = "ir kļuvis unrestrictots!"
            embed_color=0x14d121



    embed = discord.Embed(
            description=desc,
            color=embed_color)

    if osu_user == None:
        osu_user = await osuapi.get_user(name=osu_id, mode='osu', key='id')

    embed.set_author(name=osu_user['username'],
    url=f"https://osu.ppy.sh/users/{osu_user['id']}",
    icon_url=osu_user['avatar_url'])
    
    #embed.set_footer(text=member.display_name)

    await channel.send(embed=embed)

already_sent_messages = []

@tasks.loop(minutes=5)
#@bot.command()
async def link_acc():
    try:
        ctx = bot.get_channel(BOT_CHANNEL_ID)
        async with pool.acquire() as db:
            for guild in bot.guilds:
                for member in guild.members:
                    if member.activities != None:
                        for osu_activity in member.activities:
                            try:
                                if osu_activity.application_id == 367827983903490050:         
                                    username = osu_activity.large_image_text.split('(', 1)[0].removesuffix(' ')
                                    if username == osu_activity.large_image_text:
                                        continue

                                    osu_user = await osuapi.get_user(name=username, mode='osu', key='username')

                                    if osu_user == {'error': None}:
                                        continue

                                    result = await db.fetch(f'SELECT discord_id, osu_id FROM players WHERE discord_id = {member.id} AND osu_id IS NOT NULL')

                                    if result == []:

                                        if osu_user['country_code'] == 'LV':
                                            result = await db.fetch(f'SELECT discord_id, osu_id FROM players WHERE osu_id = {osu_user["id"]};')
                                            #check if discord multiaccounter
                                            if result == []:
                                                await db.execute(f'UPDATE players SET osu_id = {osu_user["id"]} WHERE discord_id = {member.id};')
                                                await ctx.send(f'Pievienoja {member.mention} datubāzei ar osu! kontu {osu_user["username"]} (id: {osu_user["id"]})', allowed_mentions = discord.AllowedMentions(users = False))
                                                await refresh_user_rank(member)
                                                continue
                                            if member.id != result[0][0]:
                                                await db.execute(f'UPDATE players SET osu_id = {osu_user["id"]} WHERE discord_id = {member.id};')
                                                await db.execute(f'UPDATE players SET osu_id = NULL WHERE discord_id = {result[0][0]};')
                                                await ctx.send(f'Lietotājs {member.mention} spēlē uz osu! konta (id: {osu_user["id"]}), kas linkots ar <@{result[0][0]}>. Vecais konts unlinkots un linkots jaunais.')
                                                await refresh_user_rank(member)

                                        else:
                                            if member.get_role(539951111382237198) == None:
                                                await member.add_roles(get(lvguild.roles, id=539951111382237198))
                                                await ctx.send(f'Lietotājs {member.mention} nav no Latvijas! (Pievienots imigranta role)')

                                    else:
                                        print(f"{member.mention} jau eksistē datubāzē")

                                        #check if osu multiaccount (datbase osu_id != activity osu_id)
                                        print(result[0][1])
                                        if osu_user['id'] != result[0][1]:
                                            if (osu_user['id'], result[0][1]) not in already_sent_messages:
                                                await ctx.send(f'Lietotājs {member.mention} jau eksistē ar osu! id {result[0][1]}, bet pašlaik spēlē uz cita osu! konta ar id = {osu_user["id"]}.')
                                                already_sent_messages.append((osu_user['id'], result[0][1]))
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

                
        print('link acc finished')

    except Exception as e:
        print(repr(e))
        await ctx.send(f'{repr(e)} in link_acc')

@tasks.loop(minutes=5)
#@bot.command()
async def refresh_roles():
    try:
        ctx = bot.get_channel(BOT_CHANNEL_ID)
        async with pool.acquire() as db:
            cursor = ''
            ranking = []
            for i in range(20):
                response = await osuapi.get_rankings(mode='osu', type='performance', country='LV', cursor=cursor)
                cursor = response['cursor']['page']
                ranking.extend(response['ranking'])

            ranking_id_list = [x['user']['id'] for x in ranking]

            result = await db.fetch(f'SELECT discord_id, osu_id FROM players WHERE osu_id IS NOT NULL;')
            member_id_list = [x.id for x in lvguild.members]

            for row in result:
                if row[0] not in member_id_list:
                    continue
                try:
                    country_rank = ranking_id_list.index(row[1]) + 1
                except ValueError:
                    country_rank = 99999

                current_role = [rev_roles[role.id] for role in get(lvguild.members, id=row[0]).roles if role.id in roles.values()]

                if country_rank == 99999:
                    osu_user = await osuapi.get_user(name=row[1], mode='osu', key='id')
                    if osu_user == {'error': None}:
                        #set restricted role
                        osu_api_check = await osuapi.get_user(name=2, mode='osu', key='id')
                        if osu_api_check == {'error': None}:
                            continue
                        if current_role == []:
                            await change_role(discord_id = row[0], new_role_id=roles['restricted'])
                            await send_rolechange_msg(discord_id=row[0], notikums='restricted', osu_user=osu_user)
                            continue
                        if roles[current_role[0]] != roles['restricted']:
                            await change_role(discord_id = row[0], current_role_id=roles[current_role[0]], new_role_id=roles['restricted'])
                            await send_rolechange_msg(discord_id=row[0], notikums='restricted', osu_user=osu_user)
                        
                        continue
                    if osu_user['statistics']['is_ranked'] == False:
                        #set inactive role
                        if current_role == []:
                            await change_role(discord_id = row[0], new_role_id=roles['inactive'])
                            await send_rolechange_msg(discord_id=row[0], notikums='inactive', osu_user=osu_user)
                            continue
                        if roles[current_role[0]] != roles['inactive']:
                            await change_role(discord_id = row[0], current_role_id=roles[current_role[0]], new_role_id=roles['inactive'])
                            await send_rolechange_msg(discord_id=row[0], notikums='inactive', osu_user=osu_user)
                        
                        continue
                
                
                new_role = await get_role_with_rank(country_rank)

                if current_role == []:
                    print(f"linked cilvekam nav role serverī, vajadzetu but {new_role}")
                    #set role
                    await change_role(discord_id=row[0], new_role_id=roles[new_role])
                    await send_rolechange_msg(discord_id=row[0], notikums='no_previous_role', role=new_role, osu_id=row[1])

                elif current_role[0] == 'restricted':
                    await change_role(discord_id=row[0], current_role_id=roles[current_role[0]], new_role_id=roles[new_role])
                    await send_rolechange_msg(discord_id=row[0], notikums='unrestricted', role=new_role, osu_id=row[1])
               
                elif new_role != current_role[0]:
                    if rolesvalue[new_role] < rolesvalue[current_role[0]]:
                        #set role
                        await change_role(discord_id=row[0], current_role_id=roles[current_role[0]], new_role_id=roles[new_role])
                        await send_rolechange_msg(discord_id=row[0], notikums='pacelas', role=new_role, osu_id=row[1])
                        continue
                    if rolesvalue[new_role] > rolesvalue[current_role[0]]:
                        #set role
                        await change_role(discord_id=row[0], current_role_id=roles[current_role[0]], new_role_id=roles[new_role])
                        await send_rolechange_msg(discord_id=row[0], notikums='nokritas', role=new_role, osu_id=row[1])
                        continue

        print("roles refreshed")
    except Exception as e:
        print(repr(e))
        await ctx.send(f'{repr(e)} in role refresh')


async def refresh_user_rank(member):
    async with pool.acquire() as db: 
        query = await db.fetch(f'SELECT discord_id, osu_id FROM players WHERE osu_id IS NOT NULL AND discord_id = {member.id};')
        if query != []:
            osu_user = await osuapi.get_user(name=query[0][1], mode='osu', key='id')
            new_role = await get_role_with_rank(osu_user["statistics"]["country_rank"])
            current_role = [role.id for role in member.roles if role.id in roles.values()]
            if current_role == []:
                await change_role(discord_id=member.id, new_role_id=roles[new_role])
            else:
                await change_role(discord_id=member.id, new_role_id=roles[new_role], current_role_id=current_role)
            await send_rolechange_msg(discord_id=member.id, notikums='no_previous_role', role=new_role, osu_user=osu_user)
            print(f"refreshed rank for user {member.display_name}")


@bot.command()
async def update_user(ctx):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    async with pool.acquire() as db:
        result = await db.fetch("SELECT discord_id FROM players;")
        db_id_list = [x[0] for x in result]
        users = 'Pievienoja '
        pievienots = False
        for member in lvguild.members:
            if member.id not in db_id_list:
                await db.execute(f'INSERT INTO players (discord_id) VALUES ({member.id});')
                print(f'added {member.name} to database')
                users += f'{member.name}, '
                pievienots = True
        
        if pievienots == True:
            await ctx.send(f'{users.removesuffix(", ")} datubāzei.')
        if pievienots == False:
            await ctx.send(f'Nevienu nepievienoja datubāzei.')



@bot.command()
async def check(ctx, arg):
    if ctx.channel.id != BOT_CHANNEL_ID:
        return
    print(f'check')
    await ctx.send(arg)

@bot.command()
async def desa(ctx):
    await ctx.send('<:desa:272418900111785985>')

@bot.command()
async def pervert(ctx):
    await ctx.author.add_roles(get(lvguild.roles, id=141542874301988864))
    print("added role")



@bot.command()
async def purge_roles(ctx):
    async with pool.acquire() as db:
        result = await db.fetch("SELECT discord_id FROM players WHERE osu_id IS NOT NULL;")
        db_id_list = [x[0] for x in result]
        for member in lvguild.members:
            if member.id not in db_id_list:
                current_role_id = [role.id for role in member.roles if role.id in roles.values()]
                if current_role_id != []:
                    await member.remove_roles(get(lvguild.roles, id=current_role_id[0]))
                    await ctx.send(f'purged role for {member.display_name}')
        
bot.run(DISCORD_TOKEN)

