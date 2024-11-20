import asyncpg
from config import DATABASE_URL

class Database:
    def __init__(self):
        self.pool = None

    async def setup_hook(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL, ssl="require")

    async def get_user(self, discord_id: int):
        """Get user from database with discord_id"""
        async with self.pool.acquire() as conn:
            result = await conn.fetch(
                "SELECT discord_id FROM players WHERE discord_id = $1;", discord_id
            )
            return result

    async def create_user(self, discord_id: int):
        """Create new user in database with discord_id"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO players (discord_id) VALUES ($1);", discord_id
            )
