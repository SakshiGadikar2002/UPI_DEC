#!/usr/bin/env python3
"""
Reset alert daily limits so notifications can be sent immediately.
"""
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def main():
    pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        database=os.getenv("POSTGRES_DB", "etl_tool"),
    )

    async with pool.acquire() as conn:
        # Reset per-day counters and cooldown tracking
        reset_counts = await conn.execute(
            "UPDATE alert_tracking SET alert_count_today = 0, last_alert_time = NULL"
        )
        # Optionally bump max per-day limit high so next run won't be blocked
        bumped_limits = await conn.execute(
            "UPDATE alert_rules SET max_alerts_per_day = COALESCE(max_alerts_per_day, 0) + 100"
        )

    await pool.close()

    print(f"Reset tracking rows: {reset_counts}")
    print(f"Bumped max_alerts_per_day: {bumped_limits}")


if __name__ == "__main__":
    asyncio.run(main())

