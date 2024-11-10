async def get_user(db, discord_id: int):
    """Get user from database with discord_id"""
    result = await db.fetch('SELECT discord_id FROM players WHERE discord_id = $1;', discord_id)
    return result

async def create_user(db, discord_id: int):
    """Create new user in database with discord_id"""
    await db.execute('INSERT INTO players (discord_id) VALUES ($1);', discord_id) 
