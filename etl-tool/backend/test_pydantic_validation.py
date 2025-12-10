#!/usr/bin/env python3
import asyncio
import logging
import os
from dotenv import load_dotenv
load_dotenv()
import asyncpg

from services.alert_manager import AlertManager
from models.alert import AlertDashboardResponse

logging.basicConfig(level=logging.DEBUG)

async def main():
    pool = await asyncpg.create_pool(
        host=os.getenv('POSTGRES_HOST','localhost'),
        port=int(os.getenv('POSTGRES_PORT',5432)),
        user=os.getenv('POSTGRES_USER','postgres'),
        password=os.getenv('POSTGRES_PASSWORD',''),
        database=os.getenv('POSTGRES_DB','etl_tool')
    )
    mgr = AlertManager(pool)
    data = await mgr.get_alert_dashboard_data()
    print("Raw data type:", type(data))
    print("Raw data keys:", data.keys() if isinstance(data, dict) else "not a dict")
    
    # Try to validate with Pydantic
    try:
        response = AlertDashboardResponse(**data)
        print("PASS: Pydantic validation passed")
        print("Response:", response)
    except Exception as e:
        print("FAIL: Pydantic validation failed:")
        print(str(e))
        import traceback
        traceback.print_exc()
    
    await pool.close()

if __name__ == '__main__':
    asyncio.run(main())
