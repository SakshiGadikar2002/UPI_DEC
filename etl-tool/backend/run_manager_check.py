#!/usr/bin/env python3
import asyncio
import logging
import os
from dotenv import load_dotenv
load_dotenv()
import asyncpg

from services.alert_manager import AlertManager

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('run_manager_check')

async def main():
    pool = await asyncpg.create_pool(
        host=os.getenv('POSTGRES_HOST','localhost'),
        port=int(os.getenv('POSTGRES_PORT',5432)),
        user=os.getenv('POSTGRES_USER','postgres'),
        password=os.getenv('POSTGRES_PASSWORD',''),
        database=os.getenv('POSTGRES_DB','etl_tool')
    )
    mgr = AlertManager(pool)
    res = await mgr.check_and_trigger_alerts()
    print('check_and_trigger_alerts returned:', res)
    await pool.close()

if __name__ == '__main__':
    asyncio.run(main())
