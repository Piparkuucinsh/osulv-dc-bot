"""Database schema definitions and verification helpers.

This module defines the expected schema for the `players` table and
provides functions to create it if missing and verify its structure.

Behavior:
- If the table is missing, `ensure_players_table` will create it.
- If the table exists, `verify_players_table` will check that required
  columns exist with compatible types. On mismatch, verification fails
  and raises `RuntimeError` so the application can exit safely.
"""
from typing import Dict


CREATE_PLAYERS_TABLE = """
CREATE TABLE IF NOT EXISTS players (
    discord_id BIGINT PRIMARY KEY,
    osu_id INTEGER,
    last_checked TIMESTAMP WITH TIME ZONE
);
"""


EXPECTED_COLUMNS: Dict[str, str] = {
    "discord_id": "bigint",
    "osu_id": "integer",
    "last_checked": "timestamp with time zone",
}


async def ensure_players_table(pool):
    """Ensure the `players` table exists and has the expected columns.

    - Creates the table if it does not exist.
    - Verifies the existing table's columns match expected types.

    Raises RuntimeError on verification failure.
    """
    async with pool.acquire() as conn:
        # create table if not exists (safe for existing DBs)
        await conn.execute(CREATE_PLAYERS_TABLE)

        # verify schema
        await verify_players_table(conn)


async def verify_players_table(conn):
    """Verify that the `players` table has the expected columns.

    Uses `information_schema.columns` to obtain the column data types.
    Raises RuntimeError with a descriptive message on mismatch.
    """
    rows = await conn.fetch(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'players' AND table_schema = 'public'
        """
    )

    if not rows:
        raise RuntimeError(
            "players table does not exist in schema 'public' after creation attempt"
        )

    existing = {r["column_name"]: r["data_type"] for r in rows}

    mismatches = []
    for col, expected_type in EXPECTED_COLUMNS.items():
        if col not in existing:
            mismatches.append(f"missing column: {col}")
            continue

        actual = existing[col]
        # normalize types for comparison (postgres returns 'timestamp with time zone')
        if actual != expected_type:
            mismatches.append(f"column {col} has type {actual}, expected {expected_type}")

    if mismatches:
        msg = (
            "players table schema mismatch:\n" + "\n".join(mismatches) + "\n"
            + "Refusing to continue to avoid data corruption. Please review the database schema."
        )
        raise RuntimeError(msg)
