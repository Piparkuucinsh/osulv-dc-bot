import asyncpg
from config import DATABASE_URL
from .schema import ensure_players_table


class Database:
    pool: asyncpg.Pool

    # def __init__(self):
    #     self.pool = None

    async def setup_hook(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL, ssl="prefer")

        # Ensure players table exists and matches expected schema. If verification
        # fails, raise an exception so the application can shut down safely.
        try:
            await ensure_players_table(self.pool)
        except Exception:
            # close pool if verification fails
            try:
                await self.pool.close()
            except Exception:
                pass
            raise

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
