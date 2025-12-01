"""
Quick verification script to ensure PostgreSQL and backend are properly configured
Run: python verify_setup.py
"""
import asyncio
import sys
import os
from database import (
    connect_to_postgres, 
    close_postgres_connection, 
    get_pool,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_DB
)

async def verify_setup():
    """Verify PostgreSQL connection and basic functionality"""
    print("=" * 60)
    print("Backend Setup Verification")
    print("=" * 60)
    print()
    
    try:
        # Test connection
        print("1. Testing PostgreSQL connection...")
        await connect_to_postgres()
        pool = get_pool()
        
        # Quick health check
        async with pool.acquire() as conn:
            db_name = await conn.fetchval('SELECT current_database()')
            version = await conn.fetchval('SELECT version()')
            message_count = await conn.fetchval('SELECT COUNT(*) FROM websocket_messages')
            connector_count = await conn.fetchval('SELECT COUNT(*) FROM api_connectors')
        
        print(f"   [OK] Connected to database: {db_name}")
        print(f"   [OK] PostgreSQL version: {version.split(',')[0]}")
        print(f"   [OK] Data in database: {message_count:,} messages, {connector_count} connectors")
        print()
        
        print("2. Checking required tables...")
        required_tables = [
            'websocket_messages',
            'websocket_batches',
            'api_connectors',
            'connector_status',
            'api_connector_data'
        ]
        
        async with pool.acquire() as conn:
            all_exist = True
            for table in required_tables:
                exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = $1
                    )
                """, table)
                if exists:
                    print(f"   [OK] Table '{table}' exists")
                else:
                    print(f"   [ERROR] Table '{table}' missing!")
                    all_exist = False
        
        if not all_exist:
            print("\n[ERROR] Some required tables are missing!")
            return False
        
        print()
        print("=" * 60)
        print("[OK] All checks passed! Backend is ready to run.")
        print("=" * 60)
        print()
        print("To start the backend server, run:")
        print("  uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        print()
        print("Or use:")
        print("  python main.py")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Verification failed: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure PostgreSQL is running")
        print("2. Check database credentials in database.py or environment variables")
        print("3. Run: python test_postgres_connection.py for detailed diagnostics")
        return False
    
    finally:
        try:
            await close_postgres_connection()
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(verify_setup())
    sys.exit(0 if success else 1)

