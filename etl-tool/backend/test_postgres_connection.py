"""
Test script to verify PostgreSQL connection and database setup
Run: python test_postgres_connection.py
"""
import asyncio
import sys
from database import (
    connect_to_postgres, 
    close_postgres_connection, 
    get_pool,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_DB
)
import os

async def test_connection():
    """Test PostgreSQL connection and database setup"""
    print("=" * 60)
    print("PostgreSQL Connection Test")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Host: {POSTGRES_HOST}")
    print(f"  Port: {POSTGRES_PORT}")
    print(f"  User: {POSTGRES_USER}")
    print(f"  Database: {POSTGRES_DB}")
    print(f"  Password: {'*' * len(os.getenv('POSTGRES_PASSWORD', '1972'))}")
    print()
    
    try:
        # Step 1: Connect to PostgreSQL
        print("Step 1: Connecting to PostgreSQL...")
        await connect_to_postgres()
        print("[OK] Successfully connected to PostgreSQL")
        print()
        
        # Step 2: Test connection pool
        print("Step 2: Testing connection pool...")
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval('SELECT 1')
            if result == 1:
                print("[OK] Connection pool is working")
        print()
        
        # Step 3: Check database info
        print("Step 3: Checking database information...")
        async with pool.acquire() as conn:
            db_name = await conn.fetchval('SELECT current_database()')
            db_version = await conn.fetchval('SELECT version()')
            print(f"[OK] Connected to database: {db_name}")
            print(f"   PostgreSQL version: {db_version.split(',')[0]}")
        print()
        
        # Step 4: Check tables exist
        print("Step 4: Checking required tables...")
        required_tables = [
            'websocket_messages',
            'websocket_batches',
            'api_connectors',
            'connector_status',
            'api_connector_data'
        ]
        
        async with pool.acquire() as conn:
            for table in required_tables:
                exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = $1
                    )
                """, table)
                if exists:
                    count = await conn.fetchval(f'SELECT COUNT(*) FROM {table}')
                    print(f"[OK] Table '{table}' exists ({count} rows)")
                else:
                    print(f"[ERROR] Table '{table}' does NOT exist")
        print()
        
        # Step 5: Check indexes
        print("Step 5: Checking indexes...")
        async with pool.acquire() as conn:
            indexes = await conn.fetch("""
                SELECT tablename, indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND tablename IN ('websocket_messages', 'websocket_batches', 'api_connectors', 'connector_status', 'api_connector_data')
                ORDER BY tablename, indexname
            """)
            if indexes:
                print(f"[OK] Found {len(indexes)} indexes:")
                for idx in indexes:
                    print(f"   - {idx['tablename']}.{idx['indexname']}")
            else:
                print("[WARNING] No indexes found")
        print()
        
        # Step 6: Test write operation
        print("Step 6: Testing write operation...")
        async with pool.acquire() as conn:
            test_id = await conn.fetchval("""
                INSERT INTO websocket_messages (
                    timestamp, exchange, instrument, price, data, message_type
                ) VALUES (NOW(), 'test', 'TEST-USDT', 100.50, '{"test": true}'::jsonb, 'test')
                RETURNING id
            """)
            if test_id:
                print(f"[OK] Write test successful (inserted id: {test_id})")
                
                # Clean up test data
                await conn.execute("DELETE FROM websocket_messages WHERE id = $1", test_id)
                print("[OK] Test data cleaned up")
        print()
        
        # Step 7: Test read operation
        print("Step 7: Testing read operation...")
        async with pool.acquire() as conn:
            count = await conn.fetchval('SELECT COUNT(*) FROM websocket_messages')
            print(f"[OK] Read test successful (total messages: {count})")
        print()
        
        print("=" * 60)
        print("[OK] All tests passed! PostgreSQL is properly configured.")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print("=" * 60)
        print("[ERROR] Connection test failed!")
        print("=" * 60)
        print(f"\nError: {str(e)}")
        print("\nTroubleshooting steps:")
        print("1. Ensure PostgreSQL is running")
        print("2. Check if the password is correct (default: '1972')")
        print("3. Verify PostgreSQL is listening on port 5432")
        print("4. Check if the database 'etl_tool' exists or can be created")
        print("5. Ensure the user has CREATE DATABASE permissions")
        print("\nTo set a custom password, use:")
        print("  export POSTGRES_PASSWORD='your_password'")
        print("  (Windows PowerShell: $env:POSTGRES_PASSWORD='your_password')")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        try:
            await close_postgres_connection()
            print("\n[OK] Connection closed")
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)

