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
                market_cap DECIMAL(20, 2),
                volume_24h DECIMAL(20, 2),
                price_change_24h DECIMAL(10, 4),
                market_cap_rank INTEGER,
                item_data JSONB NOT NULL,
                raw_item JSONB,
                item_index INTEGER,
                response_time_ms DECIMAL(10, 3),
                source_id VARCHAR(50),
                session_id VARCHAR(100),
                FOREIGN KEY (connector_id) REFERENCES api_connectors(connector_id) ON DELETE CASCADE
            )
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
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connector_items_coin_symbol 
            ON api_connector_items(coin_symbol)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connector_items_exchange 
            ON api_connector_items(exchange)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_connector_items_connector_timestamp 
            ON api_connector_items(connector_id, timestamp DESC)
        """)
        
        # Create alert_rules table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                alert_type VARCHAR(50) NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                description TEXT,
                
                -- Price threshold parameters
                symbol VARCHAR(50),
                price_threshold DECIMAL(20, 8),
                price_comparison VARCHAR(20),
                
                -- Volatility parameters
                volatility_percentage DECIMAL(10, 2),
                volatility_duration_minutes INTEGER,
                
                -- Data missing parameters
                data_missing_minutes INTEGER,
                api_endpoint VARCHAR(255),
                
                -- System health parameters
                health_check_type VARCHAR(100),
                threshold_value DECIMAL(20, 8),
                
                -- Notification settings
                notification_channels VARCHAR(50) DEFAULT 'email',
                email_recipients TEXT,
                slack_webhook_url TEXT,
                
                -- Alert settings
                severity VARCHAR(50) DEFAULT 'warning',
                cooldown_minutes INTEGER DEFAULT 5,
                max_alerts_per_day INTEGER,
                
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """)
        
        # Create indexes for alert_rules
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_rules_alert_type 
            ON alert_rules(alert_type)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled 
            ON alert_rules(enabled)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_rules_symbol 
            ON alert_rules(symbol)
        """)
        
        # Create alert_logs table (alert history)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_logs (
                id SERIAL PRIMARY KEY,
                rule_id INTEGER NOT NULL,
                alert_type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                severity VARCHAR(50) DEFAULT 'warning',
                status VARCHAR(50) DEFAULT 'pending',
                metadata JSONB,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                sent_at TIMESTAMP WITH TIME ZONE,
                acknowledged_at TIMESTAMP WITH TIME ZONE,
                FOREIGN KEY (rule_id) REFERENCES alert_rules(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for alert_logs
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_logs_rule_id 
            ON alert_logs(rule_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_logs_alert_type 
            ON alert_logs(alert_type)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_logs_severity 
            ON alert_logs(severity)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_logs_status 
            ON alert_logs(status)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_logs_created_at 
            ON alert_logs(created_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_logs_rule_created_at 
            ON alert_logs(rule_id, created_at DESC)
        """)
        
        # Create alert_tracking table (for cooldown and deduplication)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_tracking (
                id SERIAL PRIMARY KEY,
                rule_id INTEGER NOT NULL UNIQUE,
                last_alert_time TIMESTAMP WITH TIME ZONE,
                alert_count_today INTEGER DEFAULT 0,
                last_alert_date DATE,
                FOREIGN KEY (rule_id) REFERENCES alert_rules(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for alert_tracking
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_tracking_rule_id 
            ON alert_tracking(rule_id)
        """)
        
        # Create notification_queue table (for retry mechanism)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_queue (
                id SERIAL PRIMARY KEY,
                alert_id INTEGER NOT NULL,
                channel VARCHAR(50) NOT NULL,
                recipient VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                last_retry_at TIMESTAMP WITH TIME ZONE,
                sent_at TIMESTAMP WITH TIME ZONE,
                FOREIGN KEY (alert_id) REFERENCES alert_logs(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for notification_queue
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notification_queue_alert_id 
            ON notification_queue(alert_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notification_queue_status 
            ON notification_queue(status)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notification_queue_created_at 
            ON notification_queue(created_at DESC)
        """)
        
        # Create price_history table (for volatility calculation)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(50) NOT NULL,
                price DECIMAL(20, 8) NOT NULL,
                source VARCHAR(100),
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """)
        
        # Create indexes for price_history
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_history_symbol_timestamp 
            ON price_history(symbol, timestamp DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_history_symbol 
            ON price_history(symbol)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_history_timestamp 
            ON price_history(timestamp DESC)
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
            CREATE TABLE IF NOT EXISTS pipeline_steps (
                id SERIAL PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
                step_name VARCHAR(50) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                started_at TIMESTAMP WITH TIME ZONE,
                completed_at TIMESTAMP WITH TIME ZONE,
                details JSONB,
                error_message TEXT,
                step_order INTEGER DEFAULT 0
            )
        """)

        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_steps' AND column_name='details'
                ) THEN
                    ALTER TABLE pipeline_steps ADD COLUMN details JSONB;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_steps' AND column_name='started_at'
                ) THEN
                    ALTER TABLE pipeline_steps ADD COLUMN started_at TIMESTAMP WITH TIME ZONE;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='pipeline_steps' AND column_name='completed_at'
                ) THEN
                    ALTER TABLE pipeline_steps ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE;
                END IF;
            END $$;
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_api_id_status
            ON pipeline_runs(api_id, status, started_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pipeline_steps_run_id
            ON pipeline_steps(run_id)
        """)

        # Initialize alert_tracking for any existing rules that don't have tracking entries
        await conn.execute("""
            INSERT INTO alert_tracking (rule_id, last_alert_time, alert_count_today)
            SELECT id, NULL, 0
            FROM alert_rules
            WHERE id NOT IN (SELECT rule_id FROM alert_tracking)
            ON CONFLICT (rule_id) DO NOTHING
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
    """Create a pipeline run row and seed step placeholders."""
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    started_at = datetime.utcnow()
    next_run_at = (
        started_at + timedelta(seconds=schedule_interval_seconds)
        if schedule_interval_seconds
        else None
    )

    async with pool.acquire() as conn:
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

        # Seed step rows so updates can simply change status
        for idx, step in enumerate(PIPELINE_STEP_ORDER):
            await conn.execute(
                """
                INSERT INTO pipeline_steps (run_id, step_name, status, step_order)
                VALUES ($1, $2, 'pending', $3)
                """,
                run_id,
                step,
                idx,
            )

        return {"run_id": run_id, "started_at": started_at, "next_run_at": next_run_at}


async def log_pipeline_step(
    run_id: int, step_name: str, status: str, details: dict = None, error_message: str = None
):
    """Update a single pipeline step status with optional metadata."""
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    if step_name not in PIPELINE_STEP_ORDER:
        logger.warning(f"[PIPELINE] Unknown step '{step_name}' - skipping log")
        return

    now = datetime.utcnow()
    details_json = json.dumps(details) if details else None

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE pipeline_steps
            SET
                status = $1,
                details = COALESCE($2, details),
                error_message = $3,
                started_at = COALESCE(started_at, CASE WHEN $1 = 'running' THEN $4 ELSE started_at END),
                completed_at = CASE WHEN $1 IN ('success','failure') THEN $4 ELSE completed_at END
            WHERE run_id = $5 AND step_name = $6
            """,
            status,
            details_json,
            error_message,
            now,
            run_id,
            step_name,
        )


async def complete_pipeline_run(
    run_id: int, status: str, error_message: str = None, next_run_at: datetime = None
):
    """Mark pipeline run complete and store timing."""
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    completed_at = datetime.utcnow()

    async with pool.acquire() as conn:
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


async def get_pipeline_state(api_id: str, history_limit: int = 10):
    """Return current pipeline run + history for the given API id with all steps."""
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
        # Fetch active run (if any)
        active_run = await conn.fetchrow(
            """
            SELECT *
            FROM pipeline_runs
            WHERE api_id = $1 AND status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
            """,
            api_id,
        )

        # Fetch all history runs with complete metadata
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

        # Collect all run IDs (active + history)
        all_run_ids = []
        if active_run:
            all_run_ids.append(active_run["id"])
        for row in history_rows:
            if row["id"] not in all_run_ids:
                all_run_ids.append(row["id"])

        # Fetch steps for ALL runs in a single query
        all_steps = []
        if all_run_ids:
            all_steps = await conn.fetch(
                """
                SELECT run_id, step_name, status, started_at, completed_at, details, error_message, step_order
                FROM pipeline_steps
                WHERE run_id = ANY($1)
                ORDER BY run_id DESC, step_order ASC
                """,
                all_run_ids,
            )

        # Organize steps by run_id
        steps_by_run = {}
        for step in all_steps:
            run_id = step["run_id"]
            if run_id not in steps_by_run:
                steps_by_run[run_id] = []
            steps_by_run[run_id].append(_row_to_dict(step))

        # Process active run
        active_data = _row_to_dict(active_run) if active_run else None
        active_steps = steps_by_run.get(active_run["id"], []) if active_run else []

        # Process history runs with their steps
        history_with_steps = []
        for row in history_rows:
            run_dict = _row_to_dict(row)
            run_id = row["id"]
            run_dict["steps"] = steps_by_run.get(run_id, [])
            history_with_steps.append(run_dict)

        # For backward compatibility, also provide latest_steps
        latest_steps = []
        if not active_run and history_with_steps:
            latest_steps = history_with_steps[0].get("steps", [])

    return {
        "active_run": active_data,
        "steps": active_steps,
        "latest_steps": latest_steps,
        "history": history_with_steps,
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
