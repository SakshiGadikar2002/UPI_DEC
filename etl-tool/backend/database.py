"""
PostgreSQL database connection and configuration
"""
import asyncpg
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from typing import Optional
from datetime import datetime
import os
import json
import logging

logger = logging.getLogger(__name__)

# PostgreSQL connection settings
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "1972")
POSTGRES_DB = os.getenv("POSTGRES_DB", "etl_tool")

# Global connection pool
pool: Optional[asyncpg.Pool] = None


async def connect_to_postgres():
    """Create database connection pool and initialize tables"""
    global pool
    try:
        # First, check if database exists and create it if it doesn't
        await _ensure_database_exists()
        
        # Create connection pool to the target database
        print(f"Connecting to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}...")
        pool = await asyncpg.create_pool(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
            min_size=5,
            max_size=20,
            timeout=10  # Connection timeout in seconds
        )
        
        # Test the connection
        async with pool.acquire() as conn:
            result = await conn.fetchval('SELECT 1')
            if result != 1:
                raise RuntimeError("Connection test failed")
        
        print(f"[OK] Connected to PostgreSQL: {POSTGRES_DB}")
        
        # Initialize tables
        await _initialize_tables()
        
        return pool
    except asyncpg.exceptions.InvalidPasswordError:
        error_msg = f"[ERROR] Authentication failed for user '{POSTGRES_USER}'. Please check your password."
        print(error_msg)
        print(f"   Current password setting: {'*' * len(POSTGRES_PASSWORD)}")
        print(f"   Set POSTGRES_PASSWORD environment variable to change the password.")
        raise ConnectionError(error_msg)
    except asyncpg.exceptions.ConnectionDoesNotExistError:
        error_msg = f"[ERROR] Database '{POSTGRES_DB}' does not exist and could not be created."
        print(error_msg)
        raise ConnectionError(error_msg)
    except (asyncpg.exceptions.ConnectionFailureError, ConnectionError, OSError) as e:
        error_msg = f"[ERROR] Connection failed. Is PostgreSQL running on {POSTGRES_HOST}:{POSTGRES_PORT}?"
        print(error_msg)
        print(f"   Error details: {e}")
        raise ConnectionError(error_msg)
    except Exception as e:
        error_msg = f"[ERROR] Failed to connect to PostgreSQL: {e}"
        print(error_msg)
        print(f"   Host: {POSTGRES_HOST}")
        print(f"   Port: {POSTGRES_PORT}")
        print(f"   User: {POSTGRES_USER}")
        print(f"   Database: {POSTGRES_DB}")
        raise


async def _ensure_database_exists():
    """Create database if it doesn't exist using psycopg2 (better for CREATE DATABASE)"""
    try:
        # Use psycopg2 for database creation (handles CREATE DATABASE better)
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database='postgres'  # Connect to default database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)  # Required for CREATE DATABASE
        
        try:
            cursor = conn.cursor()
            # Check if database exists
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (POSTGRES_DB,)
            )
            db_exists = cursor.fetchone() is not None
            
            if not db_exists:
                # Create the database
                cursor.execute(f'CREATE DATABASE "{POSTGRES_DB}"')
                print(f"[OK] Created database: {POSTGRES_DB}")
            else:
                print(f"[OK] Database already exists: {POSTGRES_DB}")
            cursor.close()
        finally:
            conn.close()
    except psycopg2.errors.DuplicateDatabase:
        # Database already exists, that's fine
        print(f"[OK] Database already exists: {POSTGRES_DB}")
    except Exception as e:
        # If we can't create the database, it might already exist or there's a permission issue
        # Try to continue anyway - the connection attempt will fail if database doesn't exist
        print(f"[WARNING] Could not check/create database (may already exist): {e}")
        # Don't raise - let the connection attempt handle it


async def _initialize_tables():
    """Create tables and indexes if they don't exist"""
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    
    async with pool.acquire() as conn:
        # Create websocket_messages table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS websocket_messages (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                exchange VARCHAR(50) NOT NULL,
                instrument VARCHAR(100),
                price DECIMAL(20, 8),
                data JSONB NOT NULL,
                message_type VARCHAR(50) DEFAULT 'trade',
                latency_ms DECIMAL(10, 3),
                message_number INTEGER,
                format VARCHAR(50),
                extract_time DECIMAL(10, 6),
                transform_time DECIMAL(10, 6),
                load_time DECIMAL(10, 6),
                total_time DECIMAL(10, 6)
            )
        """)
        
        # Create indexes for websocket_messages
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_websocket_messages_timestamp 
            ON websocket_messages(timestamp DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_websocket_messages_exchange 
            ON websocket_messages(exchange)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_websocket_messages_instrument 
            ON websocket_messages(instrument)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_websocket_messages_price 
            ON websocket_messages(price)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_websocket_messages_message_number 
            ON websocket_messages(message_number)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_websocket_messages_timestamp_exchange 
            ON websocket_messages(timestamp DESC, exchange)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_websocket_messages_instrument_timestamp 
            ON websocket_messages(instrument, timestamp DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_websocket_messages_exchange_instrument_timestamp 
            ON websocket_messages(exchange, instrument, timestamp DESC)
        """)
        
        # Create websocket_batches table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS websocket_batches (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                exchange VARCHAR(50) NOT NULL,
                total_messages INTEGER NOT NULL,
                messages_per_second DECIMAL(10, 2) NOT NULL,
                instruments TEXT[],
                messages JSONB NOT NULL,
                metrics JSONB
            )
        """)
        
        # Create indexes for websocket_batches
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_websocket_batches_timestamp 
            ON websocket_batches(timestamp DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_websocket_batches_exchange 
            ON websocket_batches(exchange)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_websocket_batches_timestamp_exchange 
            ON websocket_batches(timestamp DESC, exchange)
        """)
        
        # Create api_connectors table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_connectors (
                id SERIAL PRIMARY KEY,
                connector_id VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                api_url TEXT NOT NULL,
                http_method VARCHAR(10) DEFAULT 'GET',
                headers_encrypted TEXT,
                query_params_encrypted TEXT,
                auth_type VARCHAR(50) DEFAULT 'None',
                credentials_encrypted TEXT,
                status VARCHAR(20) DEFAULT 'inactive',
                polling_interval INTEGER DEFAULT 1000,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                protocol_type VARCHAR(20),
                exchange_name VARCHAR(50)
            )
        """)
        
        # Create indexes for api_connectors
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connectors_connector_id 
            ON api_connectors(connector_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connectors_status 
            ON api_connectors(status)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connectors_created_at 
            ON api_connectors(created_at DESC)
        """)
        
        # Create connector_status table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS connector_status (
                id SERIAL PRIMARY KEY,
                connector_id VARCHAR(100) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'stopped',
                last_message_timestamp TIMESTAMP WITH TIME ZONE,
                message_count BIGINT DEFAULT 0,
                error_log TEXT,
                reconnect_attempts INTEGER DEFAULT 0,
                last_error TIMESTAMP WITH TIME ZONE,
                performance_metrics JSONB,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                FOREIGN KEY (connector_id) REFERENCES api_connectors(connector_id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for connector_status
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_connector_status_connector_id 
            ON connector_status(connector_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_connector_status_status 
            ON connector_status(status)
        """)
        
        # Create api_connector_data table to store API responses
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_connector_data (
                id SERIAL PRIMARY KEY,
                connector_id VARCHAR(100) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                exchange VARCHAR(50),
                instrument VARCHAR(100),
                price DECIMAL(20, 8),
                data JSONB NOT NULL,
                message_type VARCHAR(50) DEFAULT 'api_response',
                raw_response JSONB,
                status_code INTEGER,
                response_time_ms DECIMAL(10, 3),
                source_id VARCHAR(50),
                session_id VARCHAR(100),
                FOREIGN KEY (connector_id) REFERENCES api_connectors(connector_id) ON DELETE CASCADE
            )
        """)
        
        # Add source_id column if it doesn't exist (for existing databases)
        await conn.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='api_connector_data' AND column_name='source_id'
                ) THEN
                    ALTER TABLE api_connector_data ADD COLUMN source_id VARCHAR(50);
                END IF;
            END $$;
        """)
        
        # Add session_id column if it doesn't exist (for existing databases)
        await conn.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='api_connector_data' AND column_name='session_id'
                ) THEN
                    ALTER TABLE api_connector_data ADD COLUMN session_id VARCHAR(100);
                END IF;
            END $$;
        """)
        
        # Create indexes for api_connector_data
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connector_data_connector_id 
            ON api_connector_data(connector_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connector_data_timestamp 
            ON api_connector_data(timestamp DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connector_data_exchange 
            ON api_connector_data(exchange)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connector_data_instrument 
            ON api_connector_data(instrument)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connector_data_connector_timestamp 
            ON api_connector_data(connector_id, timestamp DESC)
        """)
        
        print("[OK] Initialized PostgreSQL tables with indexes")


async def close_postgres_connection():
    """Close database connection pool"""
    global pool
    if pool:
        await pool.close()
        pool = None
        print("PostgreSQL connection pool closed")


def get_pool():
    """Get database connection pool"""
    if pool is None:
        raise RuntimeError("Database pool not initialized. Call connect_to_postgres() first.")
    return pool


async def initialize_scheduled_connectors():
    """Initialize connector records for scheduled API jobs"""
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    
    scheduled_connectors = [
        {
            "connector_id": "binance_orderbook",
            "name": "Binance - Order Book (BTC/USDT)",
            "api_url": "https://api.binance.com/api/v3/depth?symbol=BTCUSDT",
            "exchange_name": "Binance",
            "protocol_type": "REST",
            "polling_interval": 10000
        },
        {
            "connector_id": "binance_prices",
            "name": "Binance - Current Prices",
            "api_url": "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            "exchange_name": "Binance",
            "protocol_type": "REST",
            "polling_interval": 10000
        },
        {
            "connector_id": "binance_24hr",
            "name": "Binance - 24hr Ticker",
            "api_url": "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
            "exchange_name": "Binance",
            "protocol_type": "REST",
            "polling_interval": 10000
        },
        {
            "connector_id": "coingecko_global",
            "name": "CoinGecko - Global Stats",
            "api_url": "https://api.coingecko.com/api/v3/global",
            "exchange_name": "CoinGecko",
            "protocol_type": "REST",
            "polling_interval": 10000
        },
        {
            "connector_id": "coingecko_top",
            "name": "CoinGecko - Top Coins",
            "api_url": "https://api.coingecko.com/api/v3/coins/markets",
            "exchange_name": "CoinGecko",
            "protocol_type": "REST",
            "polling_interval": 10000
        },
        {
            "connector_id": "coingecko_trending",
            "name": "CoinGecko - Trending",
            "api_url": "https://api.coingecko.com/api/v3/search/trending",
            "exchange_name": "CoinGecko",
            "protocol_type": "REST",
            "polling_interval": 10000
        },
        {
            "connector_id": "cryptocompare_multi",
            "name": "CryptoCompare - Multi Price",
            "api_url": "https://min-api.cryptocompare.com/data/pricemulti",
            "exchange_name": "CryptoCompare",
            "protocol_type": "REST",
            "polling_interval": 10000
        },
        {
            "connector_id": "cryptocompare_top",
            "name": "CryptoCompare - Top Coins",
            "api_url": "https://min-api.cryptocompare.com/data/top/mktcapfull",
            "exchange_name": "CryptoCompare",
            "protocol_type": "REST",
            "polling_interval": 10000
        }
    ]
    
    async with pool.acquire() as conn:
        for connector in scheduled_connectors:
            try:
                await conn.execute("""
                    INSERT INTO api_connectors 
                    (connector_id, name, api_url, exchange_name, protocol_type, polling_interval, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'active')
                    ON CONFLICT (connector_id) DO UPDATE SET updated_at = NOW()
                """, 
                    connector["connector_id"],
                    connector["name"],
                    connector["api_url"],
                    connector["exchange_name"],
                    connector["protocol_type"],
                    connector["polling_interval"]
                )
            except Exception as e:
                logger.error(f"Error initializing connector {connector['connector_id']}: {e}")
    
    logger.info("[OK] Initialized 8 scheduled connector records")
