from config import API_CLIENT_ID, API_CLIENT_SECRET
import aiohttp
from dotenv import set_key


class OsuApiV2:
    token = None
    session: aiohttp.ClientSession

    # def __init__(self):
    # self.session: None | aiohttp.ClientSession = None

    async def refresh_token(self):
        parameters = {
            "client_id": API_CLIENT_ID,
            "client_secret": API_CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "public",
        }
        async with self.session.post(
            "https://osu.ppy.sh/oauth/token", data=parameters
        ) as response:
            responsejson = await response.json()
            self.token = responsejson["access_token"]
            set_key(
                key_to_set="OSU_API_TOKEN", value_to_set=self.token, dotenv_path=".env"
            )  # doesnt work

    async def get_user(self, name, mode, key):
        async with self.session.get(
            f"https://osu.ppy.sh/api/v2/users/{name}/{mode}",
            params={"key": key},
            headers={"Authorization": f"Bearer {self.token}"},
        ) as response:
            return await response.json()

    async def get_rankings(self, mode, type, country, cursor):
        params = {"country": country}
        if cursor is not None:
            params["page"] = cursor

        async with self.session.get(
            f"https://osu.ppy.sh/api/v2/rankings/{mode}/{type}",
            params=params,
            headers={"Authorization": f"Bearer {self.token}"},
        ) as response:
            return await response.json()

    async def get_scores(self, mode, osu_id, type, limit):
        async with self.session.get(
            f"https://osu.ppy.sh/api/v2/users/{osu_id}/scores/{type}",
            params={"mode": mode, "limit": limit},
            headers={"Authorization": f"Bearer {self.token}"},
        ) as response:
            return await response.json()

    async def get_user_recent(self, osu_id):
        async with self.session.get(
            f"https://osu.ppy.sh/api/v2/users/{osu_id}/recent_activity",
            headers={"Authorization": f"Bearer {self.token}"},
        ) as response:
            return await response.json()

    async def get_beatmap_score(self, mode, osu_id, beatmap_id, mods=""):
        async with self.session.get(
            f"https://osu.ppy.sh/api/v2/beatmaps/{beatmap_id}/scores/users/{osu_id}",
            params={"mode": mode, "mods": mods},
            headers={"Authorization": f"Bearer {self.token}"},
        ) as response:
            return await response.json()
