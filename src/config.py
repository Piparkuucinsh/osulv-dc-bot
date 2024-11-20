import os
from dotenv import load_dotenv

load_dotenv()

# Discord configuration
if not (discord_token := os.getenv("DISCORD_TOKEN")):
    raise ValueError("DISCORD_TOKEN environment variable is required")
if not (server_id := os.getenv("SERVER_ID")):
    raise ValueError("SERVER_ID environment variable is required")
if not (channel_id := os.getenv("BOT_CHANNEL_ID")):
    raise ValueError("BOT_CHANNEL_ID environment variable is required")

DISCORD_TOKEN = discord_token
SERVER_ID = int(server_id)
BOT_CHANNEL_ID = int(channel_id)

# osu! API configuration
API_CLIENT_ID = os.getenv("API_CLIENT_ID")  # osu api client id
API_CLIENT_SECRET = os.getenv("API_CLIENT_SECRET")  # osu api client secret

# Database configuration
database_url = os.getenv("DATABASE_URL")
postgres_user = os.getenv("POSTGRES_USER")
postgres_password = os.getenv("POSTGRES_PASSWORD")
postgres_db = os.getenv("POSTGRES_DB")

DATABASE_URL = database_url if database_url else f"postgresql://{postgres_user}:{postgres_password}@db:5432/{postgres_db}"

ROLES = {
    "LV1": 202057149860282378,
    "LV5": 202061474213003265,
    "LV10": 202061507037495296,
    "LV25": 202061546787045377,
    "LV50": 202061582006485002,
    "LV100": 202061613644251136,
    "LV250": 297854952435351552,
    "LV500": 915646723588751391,
    "LV1000": 915647090581966858,
    "LVinf": 915647192755212289,
    "restricted": 348195423841943564,
    "inactive": 964604143912255509,
}

REV_ROLES = dict((v, k) for k, v in ROLES.items())
ROLES_VALUE = dict((key, count) for count, key in enumerate(ROLES.keys()))

PERVERT_ROLE = 141542874301988864

BOT_SELF_ID = 442370931772358666  # bot's discord id

BOTSPAM_CHANNEL_ID = 266580155860779009  # channel id for bot spam

# pp calculator needs int value but api returns mods as 2 characters
MODS_DICT = {
    "NF": 1,
    "EZ": 2,
    "TD": 4,
    "HD": 8,
    "HR": 16,
    "SD": 32,
    "DT": 64,
    "RL": 128,
    "HT": 256,
    "NC": 576,  # 512, Only set along with DoubleTime. i.e: NC only gives 576
    "FL": 1024,
    "AT": 2048,
    "SO": 4096,
    "AP": 8192,  # Autopilot
    "PF": 16416,  # 16384, Only set along with SuddenDeath. i.e: PF only gives 16416
}

RANK_EMOJI = {
    "XH": "<:SSplus:995050710406283354>",
    "X": "<:SS:995050712784453747>",
    "SH": "<:Splus:995050705926762517>",
    "S": "<:S_:995050707835166761>",
    "A": "<:A_:995050698221813770>",
    "B": "<:B_:995050700147015761>",
    "C": "<:C_:995050701879267378>",
    "D": "<:D_:995050703372439633>",
}

# The personal top limit determining if a score should get posted
USER_NEWBEST_LIMIT = {
    "LV1": 100,
    "LV5": 80,
    "LV10": 60,
    "LV25": 50,
    "LV50": 30,
    "LV100": 20,
    "LV250": 15,
    "LV500": 10,
    "LV1000": 5,
    "LVinf": 1,
}

ROLE_TRESHOLDS = {
    "LV1": 1,
    "LV5": 5,
    "LV10": 10,
    "LV25": 25,
    "LV50": 50,
    "LV100": 100,
    "LV250": 250,
    "LV500": 500,
    "LV1000": 1000,
}
