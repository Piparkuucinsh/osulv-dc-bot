import os
from dotenv import load_dotenv
from enum import Enum

load_dotenv()

# Discord configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SERVER_ID = int(os.getenv('SERVER_ID'))  # discord server id
BOT_CHANNEL_ID = int(os.getenv('BOT_CHANNEL_ID'))  # private channel for admin commands

# osu! API configuration
API_CLIENT_ID = os.getenv('API_CLIENT_ID')  # osu api client id
API_CLIENT_SECRET = os.getenv('API_CLIENT_SECRET')  # osu api client secret
OSU_API_TOKEN = os.getenv('OSU_API_TOKEN')

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')

ROLES = {
    'LV1': 202057149860282378,
    'LV5': 202061474213003265,
    'LV10': 202061507037495296,
    'LV25': 202061546787045377,
    'LV50': 202061582006485002,
    'LV100': 202061613644251136,
    'LV250': 297854952435351552,
    'LV500': 915646723588751391,
    'LV1000': 915647090581966858,
    'LVINF': 915647192755212289,
    'RESTRICTED': 348195423841943564,
    'INACTIVE': 964604143912255509
}

PERVERT_ROLE = 141542874301988864

BOT_SELF_ID = 442370931772358666  # bot's discord id

BOTSPAM_CHANNEL_ID = 266580155860779009  # channel id for bot spam

# pp calculator needs int value but api returns mods as 2 characters
MODS_DICT = {
    'NF': 1,
    'EZ': 2,
    'TD': 4,
    'HD': 8,
    'HR': 16,
    'SD': 32,
    'DT': 64,
    'RL': 128,
    'HT': 256,
    'NC': 576,  # 512, Only set along with DoubleTime. i.e: NC only gives 576
    'FL': 1024,
    'AT': 2048,
    'SO': 4096,
    'AP': 8192,    # Autopilot
    'PF': 16416  # 16384, Only set along with SuddenDeath. i.e: PF only gives 16416  
}

RANK_EMOJI = {
    'XH': '<:SSplus:995050710406283354>',
    'X': '<:SS:995050712784453747>',
    'SH': '<:Splus:995050705926762517>',
    'S': '<:S_:995050707835166761>',
    'A': '<:A_:995050698221813770>',
    'B': '<:B_:995050700147015761>',
    'C': '<:C_:995050701879267378>',
    'D': '<:D_:995050703372439633>'
}

# The personal top limit determining if a score should get posted
USER_NEWBEST_LIMIT = {
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