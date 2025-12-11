# Database Documentation

Complete guide to the PostgreSQL database schema for the ETL Tool.

## Table of Contents

1. [Database Setup](#database-setup)
2. [Connection Configuration](#connection-configuration)
3. [Schema Overview](#schema-overview)
4. [Tables](#tables)
5. [Indexes](#indexes)
6. [Queries](#queries)
7. [Backup & Recovery](#backup--recovery)

## Database Setup

### Prerequisites

- PostgreSQL 12 or higher installed
- psql command-line tool
- Network access to database server

### Creating the Database

```bash
# Connect to PostgreSQL as superuser
psql -U postgres

# Create the database
CREATE DATABASE etl_tool;

# Create user (if not exists)
CREATE USER postgres WITH PASSWORD '1972';

# Grant privileges
ALTER USER postgres CREATEDB;
ALTER DATABASE etl_tool OWNER TO postgres;
```

### Connection Configuration

The backend automatically connects and initializes the schema on startup.

**Connection String:**
```
postgresql://postgres:1972@localhost:5432/etl_tool
```

**Connection Pool Settings** (in `database.py`):
```python
pool = await asyncpg.create_pool(
    host='localhost',
    port=5432,
    user='postgres',
    password='1972',
    database='etl_tool',
    min_size=5,           # Minimum pool connections
    max_size=20,          # Maximum pool connections
    command_timeout=10    # Query timeout
)
```

## Schema Overview

The database contains tables for:
- API connector configurations (`api_connectors`)
- API aggregate responses (`api_connector_data`) - one row per API call
- API individual items (`api_connector_items`) - multiple rows per API call (granular data)
- WebSocket real-time messages (`websocket_messages`, `websocket_batches`)
- File uploads and processing (`files`, `file_data`)
- Connector status tracking (`connector_status`)

### Entity Relationship Diagram

```
api_connectors (1)
    ├─→ api_connector_data (many) - aggregate responses
    └─→ api_connector_items (many) - individual items from responses

websocket_messages (standalone)
websocket_batches (standalone)

files (1)
    └─→ file_data (many)
```

## Tables

### 1. api_connectors

Stores connector configurations and metadata.

```sql
CREATE TABLE api_connectors (
    id SERIAL PRIMARY KEY,
    connector_id VARCHAR(255) UNIQUE NOT NULL,
    connector_name TEXT,
    source_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Columns:**
- `id` - Auto-increment primary key
- `connector_id` - Unique identifier (e.g., "binance_orderbook")
- `connector_name` - Human-readable name
- `source_id` - Data source identifier
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp (updates on each API call)

**Sample Data:**
```sql
INSERT INTO api_connectors VALUES
(1, 'binance_orderbook', 'Binance - Order Book', 'binance', NOW(), NOW()),
(2, 'coingecko_global', 'CoinGecko - Global', 'coingecko', NOW(), NOW());
```

### 2. api_connector_data

Stores API responses and raw data.

```sql
CREATE TABLE api_connector_data (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(255),
    connector_id VARCHAR(255),
    exchange VARCHAR(255),
    instrument VARCHAR(255),
    price NUMERIC(20, 8),
    data JSONB,
    raw_response TEXT,
    message_type VARCHAR(100),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status_code INT,
    response_time_ms INT,
    FOREIGN KEY (connector_id) REFERENCES api_connectors(connector_id)
);
```

**Columns:**
- `id` - Auto-increment primary key
- `source_id` - Unique message ID
- `connector_id` - Reference to api_connectors
- `exchange` - Exchange name
- `instrument` - Trading pair (e.g., "BTC/USDT")
- `price` - Extracted price value
- `data` - JSON response body
- `raw_response` - Raw response text
- `message_type` - Message type identifier
- `timestamp` - When data was received
- `status_code` - HTTP status code
- `response_time_ms` - API response time in milliseconds

**Sample Query:**
```sql
-- Get latest prices
SELECT connector_id, price, timestamp
FROM api_connector_data
WHERE connector_id = 'binance_prices'
ORDER BY timestamp DESC
LIMIT 10;
```

### 3. api_connector_items

**NEW TABLE** - Stores individual items extracted from API responses. This provides granular, queryable data instead of storing entire JSON blobs.

```sql
CREATE TABLE api_connector_items (
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
);
```

**Purpose:** While `api_connector_data` stores one row per API call (entire response as JSON), this table stores **one row per item** in the response.

**Example:**
- Binance 24hr API returns 1000+ trading pairs → 1000+ rows inserted per run
- CoinGecko Top returns 100 coins → 100 rows inserted per run
- Every 10 seconds, **thousands of individual item rows** are added

**Columns:**
- `connector_id` - Which API (e.g., "binance_24hr", "coingecko_top")
- `api_name` - Human-readable API name
- `timestamp` - When data was received
- `exchange` - Exchange name
- `coin_name` - Full coin name (e.g., "Bitcoin")
- `coin_symbol` - Ticker symbol (e.g., "BTC")
- `price` - Current price (numeric, queryable)
- `market_cap` - Market capitalization
- `volume_24h` - 24-hour trading volume
- `price_change_24h` - 24-hour price change percentage
- `market_cap_rank` - Rank by market cap
- `item_data` - Full normalized item as JSON
- `raw_item` - Original item from API response
- `item_index` - Position in API response array
- `response_time_ms` - API response time

**Sample Queries:**
```sql
-- Get all Bitcoin data from all sources
SELECT api_name, coin_symbol, price, timestamp
FROM api_connector_items
WHERE coin_symbol = 'BTC'
ORDER BY timestamp DESC
LIMIT 50;

-- Get top 10 coins by market cap from latest run
SELECT coin_name, coin_symbol, price, market_cap_rank, timestamp
FROM api_connector_items
WHERE market_cap_rank IS NOT NULL
ORDER BY timestamp DESC, market_cap_rank ASC
LIMIT 100;

-- Count items from each API per minute
SELECT api_name, DATE_TRUNC('minute', timestamp), COUNT(*)
FROM api_connector_items
GROUP BY api_name, DATE_TRUNC('minute', timestamp)
ORDER BY timestamp DESC;

-- Get price history for a specific coin
SELECT api_name, price, timestamp
FROM api_connector_items
WHERE coin_symbol = 'ETH'
ORDER BY timestamp DESC
LIMIT 100;
```

**Indexes** (for performance):
```sql
CREATE INDEX idx_api_connector_items_connector_id ON api_connector_items(connector_id);
CREATE INDEX idx_api_connector_items_timestamp ON api_connector_items(timestamp DESC);
CREATE INDEX idx_api_connector_items_coin_symbol ON api_connector_items(coin_symbol);
CREATE INDEX idx_api_connector_items_exchange ON api_connector_items(exchange);
CREATE INDEX idx_api_connector_items_connector_timestamp ON api_connector_items(connector_id, timestamp DESC);
```

### 4. websocket_data

Stores real-time WebSocket messages.

```sql
CREATE TABLE websocket_data (
    id SERIAL PRIMARY KEY,
    connector_id VARCHAR(255),
    exchange VARCHAR(255),
    instrument VARCHAR(255),
    price NUMERIC(20, 8),
    data JSONB NOT NULL,
    raw_response TEXT,
    message_type VARCHAR(100),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_id VARCHAR(255)
);
```

**Columns:**
- `id` - Auto-increment primary key
- `connector_id` - Source connector
- `exchange` - Exchange name (e.g., "binance")
- `instrument` - Trading pair
- `price` - Extracted price
- `data` - Full message as JSON
- `raw_response` - Raw message text
- `message_type` - Message type
- `timestamp` - When received
- `source_id` - Source identifier

**Storage:** Unlimited (grows continuously)

### 5. files

Metadata for uploaded files.

```sql
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    file_size INT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'uploaded'
);
```

**Columns:**
- `id` - Primary key
- `filename` - Original file name
- `file_type` - MIME type (application/json, text/csv)
- `file_size` - Size in bytes
- `uploaded_at` - Upload timestamp
- `status` - Processing status (uploaded, processing, completed, failed)

### 5. file_data

Parsed data from uploaded files.

```sql
CREATE TABLE file_data (
    id SERIAL PRIMARY KEY,
    file_id INT REFERENCES files(id),
    row_number INT,
    data JSONB NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Columns:**
- `id` - Primary key
- `file_id` - Reference to files table
- `row_number` - Row index in file
- `data` - Parsed row as JSON
- `timestamp` - When parsed

## Indexes

Indexes for query optimization:

```sql
-- api_connector_data indexes
CREATE INDEX idx_connector_id ON api_connector_data(connector_id);
CREATE INDEX idx_timestamp ON api_connector_data(timestamp DESC);
CREATE INDEX idx_connector_timestamp ON api_connector_data(connector_id, timestamp DESC);
CREATE INDEX idx_source_id ON api_connector_data(source_id);

-- websocket_data indexes
CREATE INDEX idx_ws_connector ON websocket_data(connector_id);
CREATE INDEX idx_ws_timestamp ON websocket_data(timestamp DESC);
CREATE INDEX idx_ws_exchange ON websocket_data(exchange);

-- files indexes
CREATE INDEX idx_file_status ON files(status);
CREATE INDEX idx_file_uploaded ON files(uploaded_at DESC);

-- api_connectors indexes
CREATE INDEX idx_connector_id_unique ON api_connectors(connector_id);
```

## Queries

### Common Queries

**Get latest data from all connectors:**
```sql
SELECT DISTINCT ON (connector_id) 
    connector_id, price, timestamp
FROM api_connector_data
ORDER BY connector_id, timestamp DESC;
```

**Get data for last 24 hours:**
```sql
SELECT * FROM api_connector_data
WHERE timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;
```

**Count messages by connector:**
```sql
SELECT connector_id, COUNT(*) as total
FROM api_connector_data
GROUP BY connector_id
ORDER BY total DESC;
```

**Get average response time:**
```sql
SELECT connector_id, 
       AVG(response_time_ms) as avg_time,
       MIN(response_time_ms) as min_time,
       MAX(response_time_ms) as max_time
FROM api_connector_data
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY connector_id;
```

**Find slow APIs (>1000ms):**
```sql
SELECT connector_id, response_time_ms, timestamp
FROM api_connector_data
WHERE response_time_ms > 1000
ORDER BY response_time_ms DESC
LIMIT 100;
```

**Get table sizes:**
```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Cleanup old data (>30 days):**
```sql
DELETE FROM api_connector_data
WHERE timestamp < NOW() - INTERVAL '30 days';

DELETE FROM websocket_data
WHERE timestamp < NOW() - INTERVAL '30 days';
```

## Backup & Recovery

### Backup

```bash
# Full database backup
pg_dump -U postgres -d etl_tool > etl_tool_backup.sql

# Compressed backup
pg_dump -U postgres -d etl_tool | gzip > etl_tool_backup.sql.gz

# Backup specific table
pg_dump -U postgres -d etl_tool -t api_connector_data > connector_data.sql
```

### Restore

```bash
# Restore from SQL file
psql -U postgres -d etl_tool < etl_tool_backup.sql

# Restore from compressed backup
gunzip -c etl_tool_backup.sql.gz | psql -U postgres -d etl_tool

# Restore to new database
createdb etl_tool_restored
psql -U postgres -d etl_tool_restored < etl_tool_backup.sql
```

### Maintenance

```sql
-- Analyze query performance
ANALYZE;

-- Vacuum (cleanup)
VACUUM ANALYZE;

-- Reindex (rebuild indexes)
REINDEX DATABASE etl_tool;

-- Check table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

## Data Retention Policy

### Recommended Cleanup Schedule

```sql
-- Delete data older than 30 days (monthly)
DELETE FROM api_connector_data
WHERE timestamp < NOW() - INTERVAL '30 days';

-- Delete data older than 7 days (weekly)
DELETE FROM websocket_data
WHERE timestamp < NOW() - INTERVAL '7 days';

-- Delete processed files older than 90 days
DELETE FROM file_data
WHERE timestamp < NOW() - INTERVAL '90 days';
```

## PostgreSQL Configuration

### Performance Tuning

Edit `/etc/postgresql/12/main/postgresql.conf`:

```ini
# Connection pooling
max_connections = 200
max_prepared_transactions = 100

# Memory settings
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 64MB

# WAL settings
wal_buffers = 16MB
default_statistics_target = 100

# Query planning
random_page_cost = 1.1
effective_io_concurrency = 200
```

Then restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

## Troubleshooting

### Connection Issues

```bash
# Test connection
psql -U postgres -d etl_tool

# Check PostgreSQL status
sudo systemctl status postgresql

# View connection count
SELECT count(*) FROM pg_stat_activity;
```

### Query Performance

```sql
-- Enable query analysis
EXPLAIN ANALYZE SELECT * FROM api_connector_data LIMIT 10;

-- Find slow queries
SELECT * FROM pg_stat_statements 
ORDER BY mean_exec_time DESC;
```

### Disk Space

```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('etl_tool'));

-- Check table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

---

**Last Updated**: December 8, 2025  
**Version**: 1.0.0
