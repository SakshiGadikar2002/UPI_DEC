"""
PostgreSQL database connection and configuration
"""
import asyncpg
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from typing import Optional
from datetime import datetime, timedelta
import os
import json
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# PostgreSQL connection settings
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
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
                message_number INTEGER
            )
        """)

        # Ensure additional telemetry columns exist for websocket_messages
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'websocket_messages' AND column_name = 'latency_ms'
                ) THEN
                    ALTER TABLE websocket_messages ADD COLUMN latency_ms INTEGER;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'websocket_messages' AND column_name = 'format'
                ) THEN
                    ALTER TABLE websocket_messages ADD COLUMN format VARCHAR(50);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'websocket_messages' AND column_name = 'extract_time'
                ) THEN
                    ALTER TABLE websocket_messages ADD COLUMN extract_time DECIMAL(10, 4);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'websocket_messages' AND column_name = 'transform_time'
                ) THEN
                    ALTER TABLE websocket_messages ADD COLUMN transform_time DECIMAL(10, 4);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'websocket_messages' AND column_name = 'load_time'
                ) THEN
                    ALTER TABLE websocket_messages ADD COLUMN load_time DECIMAL(10, 4);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'websocket_messages' AND column_name = 'total_time'
                ) THEN
                    ALTER TABLE websocket_messages ADD COLUMN total_time DECIMAL(10, 4);
                END IF;
            END $$;
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
        # Removed indexes related to dropped columns

        # Create users table for authentication
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                full_name VARCHAR(255),
                password_hash TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                last_login_at TIMESTAMP WITH TIME ZONE
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
        """)

        # Create user activity logs
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                action VARCHAR(100) NOT NULL,
                ip_address VARCHAR(50),
                user_agent TEXT,
                metadata JSONB,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_logs_user_id_created_at
            ON user_logs(user_id, created_at DESC)
        """)

        # Create files table for uploaded file metadata
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id SERIAL PRIMARY KEY,
                file_id VARCHAR(100) UNIQUE NOT NULL,
                filename VARCHAR(255) NOT NULL,
                file_type VARCHAR(100),
                file_size BIGINT,
                storage_path TEXT,
                uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                status VARCHAR(50) DEFAULT 'uploaded'
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_uploaded_at
            ON files(uploaded_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_status
            ON files(status)
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
                connector_id VARCHAR(100) NOT NULL UNIQUE,
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
        
        # Clean up any duplicate entries (keep the most recent one per connector_id)
        await conn.execute("""
            DELETE FROM connector_status
            WHERE id NOT IN (
                SELECT DISTINCT ON (connector_id) id
                FROM connector_status
                ORDER BY connector_id, updated_at DESC
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
                FOREIGN KEY (connector_id) REFERENCES api_connectors(connector_id) ON DELETE CASCADE
            )
        """)

        # Ensure new metric / tracing columns exist for api_connector_data
        # These are used by save_to_database and /api/etl/active
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_data' AND column_name = 'raw_response'
                ) THEN
                    ALTER TABLE api_connector_data ADD COLUMN raw_response JSONB;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_data' AND column_name = 'status_code'
                ) THEN
                    ALTER TABLE api_connector_data ADD COLUMN status_code INTEGER;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_data' AND column_name = 'response_time_ms'
                ) THEN
                    ALTER TABLE api_connector_data ADD COLUMN response_time_ms INTEGER;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_data' AND column_name = 'source_id'
                ) THEN
                    ALTER TABLE api_connector_data ADD COLUMN source_id VARCHAR(100);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_data' AND column_name = 'session_id'
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
        # Removed indexes related to dropped columns
        
        # Create api_connector_items table for granular individual items from API responses
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_connector_items (
                id SERIAL PRIMARY KEY,
                connector_id VARCHAR(100) NOT NULL,
                api_name VARCHAR(255) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                exchange VARCHAR(50),
                coin_name VARCHAR(100),
                coin_symbol VARCHAR(20),
                price DECIMAL(20, 8),
                item_data JSONB NOT NULL,
                FOREIGN KEY (connector_id) REFERENCES api_connectors(connector_id) ON DELETE CASCADE
            )
        """)

        # Ensure additional metric columns exist for api_connector_items
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_items' AND column_name = 'market_cap'
                ) THEN
                    ALTER TABLE api_connector_items ADD COLUMN market_cap DECIMAL(20, 8);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_items' AND column_name = 'volume_24h'
                ) THEN
                    ALTER TABLE api_connector_items ADD COLUMN volume_24h DECIMAL(20, 8);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_items' AND column_name = 'price_change_24h'
                ) THEN
                    ALTER TABLE api_connector_items ADD COLUMN price_change_24h DECIMAL(20, 8);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_items' AND column_name = 'market_cap_rank'
                ) THEN
                    ALTER TABLE api_connector_items ADD COLUMN market_cap_rank INTEGER;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_items' AND column_name = 'raw_item'
                ) THEN
                    ALTER TABLE api_connector_items ADD COLUMN raw_item JSONB;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_items' AND column_name = 'item_index'
                ) THEN
                    ALTER TABLE api_connector_items ADD COLUMN item_index INTEGER;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_items' AND column_name = 'response_time_ms'
                ) THEN
                    ALTER TABLE api_connector_items ADD COLUMN response_time_ms INTEGER;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_items' AND column_name = 'source_id'
                ) THEN
                    ALTER TABLE api_connector_items ADD COLUMN source_id VARCHAR(100);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'api_connector_items' AND column_name = 'session_id'
                ) THEN
                    ALTER TABLE api_connector_items ADD COLUMN session_id VARCHAR(100);
                END IF;
            END $$;
        """)
        
        # Create pipeline_steps table for ETL tracking
        # First, drop the table if it exists but has the wrong schema (missing pipeline_name)
        await conn.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pipeline_steps') THEN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'pipeline_steps' AND column_name = 'pipeline_name') THEN
                        DROP TABLE pipeline_steps CASCADE;
                    END IF;
                END IF;
            END $$;
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_steps (
                id SERIAL PRIMARY KEY,
                pipeline_name VARCHAR(100) UNIQUE NOT NULL,
                extract_count INTEGER DEFAULT 0,
                transform_count INTEGER DEFAULT 0,
                load_count INTEGER DEFAULT 0,
                status VARCHAR(50) DEFAULT 'PENDING',
                last_run_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """)
        
        # Create index for pipeline_steps
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pipeline_steps_pipeline_name
            ON pipeline_steps(pipeline_name)
        """)

        # Create indexes for api_connector_items
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connector_items_connector_id 
            ON api_connector_items(connector_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connector_items_timestamp 
            ON api_connector_items(timestamp DESC)
        """)
        # Removed indexes related to dropped columns
        
        # Alert-related tables removed (alert_rules, alert_logs, alert_tracking, notification_queue)
        
        # price_history table removed - no longer used
        # Drop the table if it exists (for cleanup)
        await conn.execute("""
            DROP TABLE IF EXISTS price_history CASCADE
        """)

        # Pipeline run tracking for scheduled/non-realtime APIs
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id SERIAL PRIMARY KEY,
                api_id VARCHAR(100) NOT NULL,
                api_name VARCHAR(255),
                api_type VARCHAR(50) DEFAULT 'non-realtime',
                source_url TEXT,
                destination VARCHAR(255) DEFAULT 'postgres/api_connector_data',
                schedule_cron VARCHAR(100),
                schedule_interval_seconds INTEGER,
                status VARCHAR(20) DEFAULT 'pending',
                started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP WITH TIME ZONE,
                last_run_at TIMESTAMP WITH TIME ZONE,
                next_run_at TIMESTAMP WITH TIME ZONE,
                error_message TEXT
            )
        """)

        # Backfill missing columns for existing pipeline_runs (handles upgrades)
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='api_id'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN api_id VARCHAR(100) NOT NULL DEFAULT 'unknown';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='api_name'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN api_name VARCHAR(255);
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='api_type'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN api_type VARCHAR(50) DEFAULT 'non-realtime';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='source_url'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN source_url TEXT;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='destination'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN destination VARCHAR(255) DEFAULT 'postgres/api_connector_data';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='schedule_cron'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN schedule_cron VARCHAR(100);
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='schedule_interval_seconds'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN schedule_interval_seconds INTEGER;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='status'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN status VARCHAR(20) DEFAULT 'pending';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='started_at'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW();
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='completed_at'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='last_run_at'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN last_run_at TIMESTAMP WITH TIME ZONE;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='next_run_at'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN next_run_at TIMESTAMP WITH TIME ZONE;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_runs' AND column_name='error_message'
                ) THEN
                    ALTER TABLE pipeline_runs ADD COLUMN error_message TEXT;
                END IF;
            END $$;
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_api_id_status
            ON pipeline_runs(api_id, status, started_at DESC)
        """)

        # Create visualization_data table for processed visualization data
        # This table stores aggregated data specifically for visualization/monitoring
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS visualization_data (
                id SERIAL PRIMARY KEY,
                data_type VARCHAR(50) NOT NULL,  -- 'markets' or 'global_stats'
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                data JSONB NOT NULL,  -- Processed data ready for visualization
                metadata JSONB,  -- Additional metadata (coin count, etc.)
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                UNIQUE(data_type, timestamp)  -- One record per data_type per timestamp
            )
        """)

        # Create indexes for visualization_data
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_visualization_data_type_timestamp
            ON visualization_data(data_type, timestamp DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_visualization_data_timestamp
            ON visualization_data(timestamp DESC)
        """)

        # Create failed_api_calls table for observability
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS failed_api_calls (
                id SERIAL PRIMARY KEY,
                api_id VARCHAR(100) NOT NULL,
                api_name VARCHAR(255),
                url TEXT,
                method VARCHAR(10) DEFAULT 'GET',
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                error_message TEXT NOT NULL,
                status_code INTEGER,
                response_time_ms INTEGER,
                pipeline_run_id INTEGER,
                step_name VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """)

        # Create indexes for failed_api_calls
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_failed_api_calls_api_id
            ON failed_api_calls(api_id, timestamp DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_failed_api_calls_timestamp
            ON failed_api_calls(timestamp DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_failed_api_calls_pipeline_run_id
            ON failed_api_calls(pipeline_run_id)
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


# -------- Pipeline tracking helpers --------
# Order is aligned to a classic ETL pipeline
PIPELINE_STEP_ORDER = ["extract", "clean", "transform", "load"]


async def start_pipeline_run(
    api_id: str,
    api_name: str,
    source_url: str,
    api_type: str = "non-realtime",
    schedule_interval_seconds: int = None,
    schedule_cron: str = None,
    destination: str = "postgres/api_connector_data",
):
    """
    Create a pipeline run row.
    NOTE: Updated to work with new pipeline_steps schema. 
    We primarily update the single source of truth pipeline_steps table.
    We also keep a record in pipeline_runs for history if needed, but we don't link steps to it anymore.
    """
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    started_at = datetime.utcnow()
    next_run_at = (
        started_at + timedelta(seconds=schedule_interval_seconds)
        if schedule_interval_seconds
        else None
    )

    async with pool.acquire() as conn:
        # Insert into pipeline_runs for history tracking
        run_id = await conn.fetchval(
            """
            INSERT INTO pipeline_runs (
                api_id, api_name, api_type, source_url, destination,
                schedule_cron, schedule_interval_seconds, status,
                started_at, last_run_at, next_run_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'running', $8, $8, $9)
            RETURNING id
            """,
            api_id,
            api_name,
            api_type,
            source_url,
            destination,
            schedule_cron,
            schedule_interval_seconds,
            started_at,
            next_run_at,
        )

        # Update the single source of truth table (pipeline_steps)
        # Set status to RUNNING but preserve existing counts (they accumulate over time)
        await conn.execute("""
            INSERT INTO pipeline_steps (pipeline_name, status, last_run_at)
            VALUES ($1, 'RUNNING', $2)
            ON CONFLICT (pipeline_name) 
            DO UPDATE SET status = 'RUNNING', last_run_at = $2
        """, api_id, started_at)

        return {"run_id": run_id, "started_at": started_at, "next_run_at": next_run_at}


async def log_pipeline_step(
    run_id: int, step_name: str, status: str, details: dict = None, error_message: str = None
):
    """
    Update pipeline status.
    NOTE: Updated to use new pipeline_steps schema.
    Since we don't have run_id in pipeline_steps, we map based on active pipeline (this is best effort).
    Ideally, this function should take api_id, but we keep signature for compatibility.
    """
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    if step_name not in PIPELINE_STEP_ORDER:
        logger.warning(f"[PIPELINE] Unknown step '{step_name}' - skipping log")
        return

    # We can't easily map run_id to api_id without a query, but this function is likely legacy now.
    # The new scheduler updates pipeline_steps directly.
    # For safety, we just log a warning and return, or try to find the api_id from pipeline_runs.
    
    async with pool.acquire() as conn:
        try:
            # Try to find which API this run belongs to
            api_id = await conn.fetchval("SELECT api_id FROM pipeline_runs WHERE id = $1", run_id)
            
            if api_id:
                # Update global status if it's a significant step change
                # This is a rough mapping
                pass
        except Exception as e:
            logger.warning(f"Failed to log pipeline step legacy: {e}")


async def complete_pipeline_run(
    run_id: int, status: str, error_message: str = None, next_run_at: datetime = None
):
    """Mark pipeline run complete and store timing."""
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    completed_at = datetime.utcnow()

    async with pool.acquire() as conn:
        # Update history
        await conn.execute(
            """
            UPDATE pipeline_runs
            SET status = $1,
                completed_at = $2,
                error_message = $3,
                last_run_at = COALESCE(last_run_at, $2),
                next_run_at = COALESCE($4, next_run_at)
            WHERE id = $5
            """,
            status,
            completed_at,
            error_message,
            next_run_at,
            run_id,
        )
        
        # Also update the main pipeline_steps table if possible
        try:
            api_id = await conn.fetchval("SELECT api_id FROM pipeline_runs WHERE id = $1", run_id)
            if api_id:
                pipeline_status = 'COMPLETED' if status == 'success' else 'FAILED'
                await conn.execute("""
                    UPDATE pipeline_steps 
                    SET status = $1 
                    WHERE pipeline_name = $2
                """, pipeline_status, api_id)
        except Exception:
            pass


async def update_pipeline_counts(connector_id: str):
    """
    Update pipeline_steps counts immediately after data is saved.
    This ensures counts are updated in real-time instead of waiting for the tracker.
    Uses a fresh connection to ensure we see committed data.
    """
    if pool is None:
        logger.warning(f"[PIPELINE] Pool not available, cannot update counts for {connector_id}")
        return
    
    try:
        # Use a fresh connection to ensure we see all committed data
        async with pool.acquire() as conn:
            # Calculate current counts from database tables
            extract_count = await conn.fetchval("""
                SELECT COUNT(*) FROM api_connector_data WHERE connector_id = $1
            """, connector_id) or 0
            
            transform_count = await conn.fetchval("""
                SELECT COUNT(*) FROM api_connector_items WHERE connector_id = $1
            """, connector_id) or 0
            
            load_count = transform_count  # Items are loaded to DB, so same as transform
            
            # Update pipeline_steps with current counts (preserve status and last_run_at if they exist)
            await conn.execute("""
                INSERT INTO pipeline_steps (pipeline_name, extract_count, transform_count, load_count)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (pipeline_name) 
                DO UPDATE SET 
                    extract_count = $2,
                    transform_count = $3,
                    load_count = $4
            """, connector_id, extract_count, transform_count, load_count)
            
            logger.info(f"[PIPELINE] ✅ Updated counts for {connector_id}: RECORDS={extract_count}, ITEMS={transform_count}")
            print(f"[PIPELINE] ✅ Updated counts for {connector_id}: RECORDS={extract_count}, ITEMS={transform_count}")
    except Exception as e:
        logger.error(f"[PIPELINE] ❌ Failed to update counts for {connector_id}: {e}", exc_info=True)
        print(f"[PIPELINE] ❌ Failed to update counts for {connector_id}: {e}")


async def get_pipeline_state(api_id: str, history_limit: int = 10):
    """
    Return current pipeline run + history for the given API id.
    ADAPTED for new pipeline_steps schema (single source of truth).
    """
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    def _row_to_dict(row):
        row_dict = dict(row)
        # Attempt to parse JSON for details if stringified
        if "details" in row_dict and isinstance(row_dict["details"], str):
            try:
                row_dict["details"] = json.loads(row_dict["details"])
            except Exception:
                pass
        return row_dict

    async with pool.acquire() as conn:
        # 1. Fetch from new pipeline_steps table (Single Source of Truth)
        step_row = await conn.fetchrow(
            "SELECT * FROM pipeline_steps WHERE pipeline_name = $1", 
            api_id
        )
        
        # 2. Fetch connector details for metadata
        connector = await conn.fetchrow(
            "SELECT * FROM api_connectors WHERE connector_id = $1", 
            api_id
        )
        
        # 3. Fetch recent history from pipeline_runs (optional, but good for charts)
        history_rows = await conn.fetch(
            """
            SELECT *
            FROM pipeline_runs
            WHERE api_id = $1
            ORDER BY started_at DESC
            LIMIT $2
            """,
            api_id,
            history_limit,
        )
        
        # Construct active_run object compatible with frontend
        active_run = None
        
        # If we have a record in pipeline_steps, we build the view from it
        if step_row:
            status = step_row['status']
            last_run = step_row['last_run_at']
            
            # Map counts to steps for frontend visualization
            steps = [
                {
                    "step_name": "extract",
                    "status": "success" if step_row['extract_count'] > 0 else ("running" if status == "RUNNING" else "pending"),
                    "details": {"count": step_row['extract_count']},
                    "step_order": 0,
                    "started_at": last_run,
                    "completed_at": last_run if step_row['extract_count'] > 0 else None
                },
                {
                    "step_name": "transform",
                    "status": "success" if step_row['transform_count'] > 0 else ("running" if status == "RUNNING" else "pending"),
                    "details": {"count": step_row['transform_count']},
                    "step_order": 1,
                    "started_at": last_run,
                    "completed_at": last_run if step_row['transform_count'] > 0 else None
                },
                {
                    "step_name": "load",
                    "status": "success" if step_row['load_count'] > 0 else ("running" if status == "RUNNING" else "pending"),
                    "details": {"count": step_row['load_count']},
                    "step_order": 2,
                    "started_at": last_run,
                    "completed_at": last_run if step_row['load_count'] > 0 else None
                }
            ]
            
            if connector:
                active_run = {
                    "id": 0, # Placeholder
                    "api_id": api_id,
                    "api_name": connector['name'],
                    "api_type": "realtime",
                    "source_url": connector['api_url'],
                    "destination": "postgres/api_connector_data",
                    "status": status.lower(),
                    "started_at": last_run,
                    "completed_at": last_run if status == 'COMPLETED' else None,
                    "schedule_interval_seconds": connector['polling_interval'] // 1000 if connector['polling_interval'] else 60,
                    "steps": steps
                }

        # If no active run from pipeline_steps (maybe first load), try to fall back to connector info
        if not active_run and connector:
             active_run = {
                "id": 0,
                "api_id": api_id,
                "api_name": connector['name'],
                "status": "idle",
                "steps": []
             }

        # Map history rows
        history = [dict(row) for row in history_rows]

        return {
            "active_run": active_run,
            "steps": active_run['steps'] if active_run and 'steps' in active_run else [],
            "latest_steps": active_run['steps'] if active_run and 'steps' in active_run else [],
            "history": history
        }


# -------- User helpers --------
async def get_user_by_email(email: str):
    """Fetch a user by email"""
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, email, full_name, password_hash, is_active, created_at, last_login_at FROM users WHERE email = $1",
            email.lower()
        )


async def create_user(email: str, password_hash: str, full_name: Optional[str] = None) -> int:
    """Create a new user and return its id"""
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO users (email, full_name, password_hash)
            VALUES ($1, $2, $3)
            ON CONFLICT (email) DO NOTHING
            RETURNING id
            """,
            email.lower(),
            full_name,
            password_hash
        )


async def update_user_last_login(user_id: int):
    """Set the last_login_at timestamp for a user"""
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET last_login_at = NOW() WHERE id = $1",
            user_id
        )


async def log_user_event(user_id: int, action: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None, metadata: Optional[dict] = None):
    """Record a user activity event"""
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_logs (user_id, action, ip_address, user_agent, metadata)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id,
            action,
            ip_address,
            user_agent,
            json.dumps(metadata) if metadata else None
        )


# -------- File upload helpers --------
async def save_uploaded_file_metadata(
    file_id: str,
    filename: str,
    file_type: str,
    file_size: int,
    storage_path: str,
    status: str = "uploaded",
):
    """Persist uploaded file metadata so uploads are traceable in the database."""
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO files (file_id, filename, file_type, file_size, storage_path, status)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (file_id) DO NOTHING
            RETURNING id
            """,
            file_id,
            filename,
            file_type,
            file_size,
            storage_path,
            status,
        )


async def log_failed_api_call(
    api_id: str,
    api_name: str,
    url: str,
    method: str,
    error_message: str,
    status_code: int = None,
    response_time_ms: int = None,
    pipeline_run_id: int = None,
    step_name: str = None,
):
    """Log a failed API call to the failed_api_calls table for observability."""
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO failed_api_calls (
                    api_id, api_name, url, method, timestamp, error_message,
                    status_code, response_time_ms, pipeline_run_id, step_name
                )
                VALUES ($1, $2, $3, $4, NOW(), $5, $6, $7, $8, $9)
                """,
                api_id,
                api_name,
                url,
                method,
                error_message,
                status_code,
                response_time_ms,
                pipeline_run_id,
                step_name,
            )
    except Exception as e:
        logger.error(f"[FAILED_API] Failed to log failed API call for {api_id}: {e}")


async def get_failed_api_calls(api_id: str = None, limit: int = 100):
    """Get failed API calls, optionally filtered by api_id."""
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    
    async with pool.acquire() as conn:
        if api_id:
            rows = await conn.fetch(
                """
                SELECT id, api_id, api_name, url, method, timestamp, error_message,
                       status_code, response_time_ms, pipeline_run_id, step_name, created_at
                FROM failed_api_calls
                WHERE api_id = $1
                ORDER BY timestamp DESC
                LIMIT $2
                """,
                api_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, api_id, api_name, url, method, timestamp, error_message,
                       status_code, response_time_ms, pipeline_run_id, step_name, created_at
                FROM failed_api_calls
                ORDER BY timestamp DESC
                LIMIT $1
                """,
                limit,
            )
        return [dict(row) for row in rows]


async def update_file_status(file_id: str, status: str):
    """Update the status of an uploaded file (e.g., processing, completed)."""
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE files SET status = $1 WHERE file_id = $2",
            status,
            file_id,
        )
