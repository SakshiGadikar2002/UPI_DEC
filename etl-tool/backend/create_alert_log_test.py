#!/usr/bin/env python3
"""
Test script to directly create an alert log entry using AlertManager._create_alert_log
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
import asyncpg

from services.alert_manager import AlertManager

async def main():
    pool = await asyncpg.create_pool(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
        database=os.getenv('POSTGRES_DB', 'etl_tool')
    )

    mgr = AlertManager(pool)

    # Use rule_id 2 if exists, otherwise list rules
    async with pool.acquire() as conn:
        rule = await conn.fetchrow('SELECT id, name FROM alert_rules ORDER BY id DESC LIMIT 1')
        if not rule:
            print('No alert rules found to attach test alert to')
            await pool.close()
            return
        rule_id = rule['id']
        print(f'Using rule id={rule_id} ({rule["name"]})')

    metadata = {'test': True, 'note': 'create_alert_log_test'}

    alert_id = await mgr._create_alert_log(rule_id, 'price_threshold', 'Test Insert', 'This is a test', 'critical', metadata)
    print('create_alert_log returned:', alert_id)

    # Verify entry in DB
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT id, rule_id, title, message, severity, metadata, created_at FROM alert_logs WHERE id = $1', alert_id)
        print('Inserted alert log row:')
        print(row)

    await pool.close()

if __name__ == '__main__':
    asyncio.run(main())
