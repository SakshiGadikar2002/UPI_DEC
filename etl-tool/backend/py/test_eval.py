#!/usr/bin/env python3
import asyncio
from dotenv import load_dotenv
import os
import asyncpg

load_dotenv()

from services.alert_checker import AlertChecker

async def main():
    pool = await asyncpg.create_pool(
        host=os.getenv('POSTGRES_HOST','localhost'),
        port=int(os.getenv('POSTGRES_PORT',5432)),
        user=os.getenv('POSTGRES_USER','postgres'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB','etl_tool')
    )
    checker = AlertChecker(pool)
    price = await checker.get_current_price('BTC')
    print('current_price ->', price)
    triggered, msg = await checker.check_price_threshold('BTC', price, 50000, 'greater')
    print('triggered ->', triggered, 'msg ->', msg)
    await pool.close()

asyncio.run(main())
