#!/usr/bin/env python3
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
import asyncpg

async def check_emails():
    pool = await asyncpg.create_pool(
        host='localhost', port=5432, user='postgres',
        password='1972', database='etl_tool'
    )
    async with pool.acquire() as conn:
        rules = await conn.fetch('SELECT id, name, email_recipients FROM alert_rules')
        for r in rules:
            print(f"Rule {r['id']}: {r['name']}")
            print(f"  Recipients: {r['email_recipients']}")
        
        # Check recent alert logs with status
        logs = await conn.fetch('''
            SELECT id, rule_id, created_at, sent_at, status 
            FROM alert_logs 
            ORDER BY created_at DESC 
            LIMIT 3
        ''')
        print("\nRecent Alert Logs:")
        for log in logs:
            print(f"  Alert {log['id']}: Rule {log['rule_id']} - Status: {log['status']} - Sent: {log['sent_at']}")
    
    await pool.close()

asyncio.run(check_emails())
