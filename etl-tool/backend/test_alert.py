"""
Test script to insert test price data and trigger alert
"""
import asyncio
import asyncpg
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def insert_test_price():
    """Insert test price data for alert testing"""
    
    # Connection details
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = int(os.getenv('POSTGRES_PORT', 5432))
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', '1972')
    database = os.getenv('POSTGRES_DB', 'etl_tool')
    
    try:
        # Connect to database
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        # First, try inserting into api_connector_items (main price table)
        try:
            await conn.execute('''
                INSERT INTO api_connector_items (coin_symbol, price, timestamp)
                VALUES ('BTC', $1, $2)
            ''', 51000, datetime.now())
            print("✅ Test price data inserted into api_connector_items!")
        except Exception as e:
            print(f"Note: api_connector_items may not exist yet: {e}")
            print("Trying price_history table instead...")
            # Fallback to price_history
            await conn.execute('''
                INSERT INTO price_history (symbol, price, source, timestamp)
                VALUES ('BTC', $1, 'test_alert', $2)
            ''', 51000, datetime.now())
            print("✅ Test price data inserted into price_history!")
        
        print("   Symbol: BTC")
        print("   Price: 51000 (above threshold of 50000)")
        
        # Verify insertion
        row = await conn.fetchrow('''
            SELECT price 
            FROM api_connector_items 
            WHERE coin_symbol = 'BTC'
            ORDER BY timestamp DESC 
            LIMIT 1
        ''')
        
        if not row:
            row = await conn.fetchrow('''
                SELECT price 
                FROM price_history 
                WHERE symbol = 'BTC'
                ORDER BY timestamp DESC 
                LIMIT 1
            ''')
        
        if row:
            print(f"\n✅ Verified in database:")
            print(f"   {row}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(insert_test_price())
