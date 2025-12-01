"""
Script to export all WebSocket messages from PostgreSQL to CSV
This will show you ALL messages, not just 1000
"""
import asyncio
import asyncpg
import csv
from datetime import datetime
import os

# Database connection settings
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "1972")
POSTGRES_DB = os.getenv("POSTGRES_DB", "etl_tool")


async def export_all_messages():
    """Export all messages to CSV"""
    try:
        # Connect to database
        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )
        
        # Get total count
        total = await conn.fetchval("SELECT COUNT(*) FROM websocket_messages")
        print(f"📊 Total messages in database: {total}")
        
        # Fetch ALL messages
        print("⏳ Fetching all messages...")
        rows = await conn.fetch("""
            SELECT id, timestamp, exchange, instrument, price, data, message_type
            FROM websocket_messages
            ORDER BY id ASC
        """)
        
        print(f"✅ Fetched {len(rows)} messages")
        
        # Export to CSV
        filename = f"all_messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(['id', 'timestamp', 'exchange', 'instrument', 'price', 'message_type', 'data'])
            
            # Write rows
            for row in rows:
                writer.writerow([
                    row['id'],
                    row['timestamp'],
                    row['exchange'],
                    row['instrument'],
                    row['price'],
                    row['message_type'],
                    str(row['data'])[:200]  # First 200 chars of JSON data
                ])
        
        print(f"✅ Exported all {len(rows)} messages to: {filename}")
        print(f"📁 File location: {os.path.abspath(filename)}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(export_all_messages())

