from config import API_CLIENT_ID, API_CLIENT_SECRET
import aiohttp
import time
import functools
from typing import Callable


def ensure_valid_token(func: Callable):
    """Decorator to ensure token is valid before making API calls"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        self = args[0]
        current_time = time.time()
        if (
            self.token is None
            or (current_time - self.last_token_refresh) >= self.token_refresh_interval
        ):
            await self.refresh_token()
        return await func(*args, **kwargs)

    return wrapper


class OsuApiV2:
    token: str | None = None
    session: aiohttp.ClientSession
    last_token_refresh = 0
    token_refresh_interval: int

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
            self.last_token_refresh = time.time()
            self.token_refresh_interval = responsejson["expires_in"] - 60

    @ensure_valid_token
    async def get_user(self, name, mode, key):
        async with self.session.get(
            f"https://osu.ppy.sh/api/v2/users/{name}/{mode}",
            params={"key": key},
            headers={"Authorization": f"Bearer {self.token}"},
        ) as response:
            return await response.json()

    @ensure_valid_token
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

    @ensure_valid_token
    async def get_scores(self, mode, osu_id, type, limit):
        async with self.session.get(
            f"https://osu.ppy.sh/api/v2/users/{osu_id}/scores/{type}",
            params={"mode": mode, "limit": limit},
            headers={"Authorization": f"Bearer {self.token}"},
        ) as response:
            return await response.json()

    @ensure_valid_token
    async def get_user_recent(self, osu_id):
        async with self.session.get(
            f"https://osu.ppy.sh/api/v2/users/{osu_id}/recent_activity",
            headers={"Authorization": f"Bearer {self.token}"},
        ) as response:
            return await response.json()

    @ensure_valid_token
    async def get_beatmap_score(self, mode, osu_id, beatmap_id, mods=""):
        async with self.session.get(
            f"https://osu.ppy.sh/api/v2/beatmaps/{beatmap_id}/scores/users/{osu_id}",
            params={"mode": mode, "mods": mods},
            headers={"Authorization": f"Bearer {self.token}"},
        ) as response:
            return await response.json()
