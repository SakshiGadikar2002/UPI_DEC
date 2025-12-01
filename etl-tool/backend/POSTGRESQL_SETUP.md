# PostgreSQL Database Setup and Schema Documentation

Complete guide for PostgreSQL database configuration, schema, and management.

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Database Schema](#database-schema)
4. [Indexes](#indexes)
5. [Connection Management](#connection-management)
6. [Data Management](#data-management)
7. [Performance Optimization](#performance-optimization)
8. [Backup and Recovery](#backup-and-recovery)
9. [Troubleshooting](#troubleshooting)

## Installation

### Windows

1. Download PostgreSQL from https://www.postgresql.org/download/windows/
2. Run the installer
3. Remember the password you set for the `postgres` user
4. PostgreSQL runs as a Windows service by default

### macOS

```bash
brew install postgresql@17
brew services start postgresql@17
```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## Configuration

### Environment Variables

```bash
# Windows PowerShell
$env:POSTGRES_HOST="localhost"
$env:POSTGRES_PORT="5432"
$env:POSTGRES_USER="postgres"
$env:POSTGRES_PASSWORD="your_password"
$env:POSTGRES_DB="etl_tool"

# Linux/macOS
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="your_password"
export POSTGRES_DB="etl_tool"
```

### Default Configuration

- **Host**: `localhost`
- **Port**: `5432`
- **User**: `postgres`
- **Password**: Set in `database.py` or environment variable
- **Database**: `etl_tool` (auto-created)

### Connection Pool Settings

```python
pool = await asyncpg.create_pool(
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    database=POSTGRES_DB,
    min_size=5,      # Minimum connections
    max_size=20,     # Maximum connections
    timeout=10       # Connection timeout (seconds)
)
```

## Database Schema

### Table: `websocket_messages`

Stores individual real-time WebSocket messages.

```sql
CREATE TABLE websocket_messages (
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
);
```

**Columns**:
- `id`: Primary key (auto-increment)
- `timestamp`: Message timestamp with timezone
- `exchange`: Exchange name (okx, binance, custom)
- `instrument`: Trading pair (BTC-USDT, ETH-USDT, etc.)
- `price`: Price value (if available)
- `data`: Complete message data (JSONB)
- `message_type`: Type of message (trade, ticker, etc.)
- `latency_ms`: Message latency in milliseconds
- `message_number`: Sequential message number
- `format`: Data format (OKX, Binance, etc.)
- `extract_time`: ETL extract time
- `transform_time`: ETL transform time
- `load_time`: ETL load time
- `total_time`: Total processing time

### Table: `websocket_batches`

Stores batched messages with aggregated metrics.

```sql
CREATE TABLE websocket_batches (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    exchange VARCHAR(50) NOT NULL,
    total_messages INTEGER NOT NULL,
    messages_per_second DECIMAL(10, 2) NOT NULL,
    instruments TEXT[],
    messages JSONB NOT NULL,
    metrics JSONB
);
```

**Columns**:
- `id`: Primary key
- `timestamp`: Batch timestamp
- `exchange`: Exchange name
- `total_messages`: Number of messages in batch
- `messages_per_second`: Throughput metric
- `instruments`: Array of instruments in batch
- `messages`: All messages in batch (JSONB)
- `metrics`: Additional metrics (JSONB)

### Table: `api_connectors`

Stores API connector configurations.

```sql
CREATE TABLE api_connectors (
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
);
```

**Columns**:
- `id`: Primary key
- `connector_id`: Unique connector identifier
- `name`: Connector name
- `api_url`: API endpoint URL
- `http_method`: HTTP method (GET, POST, etc.)
- `headers_encrypted`: Encrypted custom headers
- `query_params_encrypted`: Encrypted query parameters
- `auth_type`: Authentication type
- `credentials_encrypted`: Encrypted credentials
- `status`: Connector status (inactive, running, stopped, error)
- `polling_interval`: Polling interval in milliseconds
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `protocol_type`: Protocol type (REST, WebSocket)
- `exchange_name`: Exchange name (if applicable)

### Table: `connector_status`

Tracks runtime status of connectors.

```sql
CREATE TABLE connector_status (
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
);
```

**Columns**:
- `id`: Primary key
- `connector_id`: Foreign key to api_connectors
- `status`: Current status
- `last_message_timestamp`: Timestamp of last message
- `message_count`: Total messages processed
- `error_log`: Error log text
- `reconnect_attempts`: Number of reconnection attempts
- `last_error`: Timestamp of last error
- `performance_metrics`: Performance metrics (JSONB)
- `updated_at`: Last update timestamp

### Table: `api_connector_data`

Stores data collected from API connectors.

```sql
CREATE TABLE api_connector_data (
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
);
```

**Columns**:
- `id`: Primary key
- `connector_id`: Foreign key to api_connectors
- `timestamp`: Data timestamp
- `exchange`: Exchange name
- `instrument`: Trading pair
- `price`: Price value
- `data`: Processed data (JSONB)
- `message_type`: Message type
- `raw_response`: Raw API response (JSONB)
- `status_code`: HTTP status code
- `response_time_ms`: Response time in milliseconds
- `source_id`: Unique source identifier
- `session_id`: Session identifier

## Indexes

### websocket_messages Indexes

```sql
-- Primary timestamp index
CREATE INDEX idx_websocket_messages_timestamp 
ON websocket_messages(timestamp DESC);

-- Exchange index
CREATE INDEX idx_websocket_messages_exchange 
ON websocket_messages(exchange);

-- Instrument index
CREATE INDEX idx_websocket_messages_instrument 
ON websocket_messages(instrument);

-- Price index
CREATE INDEX idx_websocket_messages_price 
ON websocket_messages(price);

-- Message number index
CREATE INDEX idx_websocket_messages_message_number 
ON websocket_messages(message_number);

-- Composite indexes for common queries
CREATE INDEX idx_websocket_messages_timestamp_exchange 
ON websocket_messages(timestamp DESC, exchange);

CREATE INDEX idx_websocket_messages_instrument_timestamp 
ON websocket_messages(instrument, timestamp DESC);

CREATE INDEX idx_websocket_messages_exchange_instrument_timestamp 
ON websocket_messages(exchange, instrument, timestamp DESC);
```

### websocket_batches Indexes

```sql
CREATE INDEX idx_websocket_batches_timestamp 
ON websocket_batches(timestamp DESC);

CREATE INDEX idx_websocket_batches_exchange 
ON websocket_batches(exchange);

CREATE INDEX idx_websocket_batches_timestamp_exchange 
ON websocket_batches(timestamp DESC, exchange);
```

### api_connectors Indexes

```sql
CREATE INDEX idx_api_connectors_connector_id 
ON api_connectors(connector_id);

CREATE INDEX idx_api_connectors_status 
ON api_connectors(status);

CREATE INDEX idx_api_connectors_created_at 
ON api_connectors(created_at DESC);
```

### connector_status Indexes

```sql
CREATE INDEX idx_connector_status_connector_id 
ON connector_status(connector_id);

CREATE INDEX idx_connector_status_status 
ON connector_status(status);
```

### api_connector_data Indexes

```sql
CREATE INDEX idx_api_connector_data_connector_id 
ON api_connector_data(connector_id);

CREATE INDEX idx_api_connector_data_timestamp 
ON api_connector_data(timestamp DESC);

CREATE INDEX idx_api_connector_data_exchange 
ON api_connector_data(exchange);

CREATE INDEX idx_api_connector_data_instrument 
ON api_connector_data(instrument);

CREATE INDEX idx_api_connector_data_connector_timestamp 
ON api_connector_data(connector_id, timestamp DESC);
```

## Connection Management

### Automatic Database Creation

The backend automatically creates the database if it doesn't exist:

```python
async def _ensure_database_exists():
    # Checks if database exists
    # Creates if it doesn't exist
    # Uses psycopg2 for CREATE DATABASE
```

### Connection Pooling

Connection pooling is managed by asyncpg:

- **Min Size**: 5 connections (always available)
- **Max Size**: 20 connections (scales up as needed)
- **Timeout**: 10 seconds (connection timeout)

### Connection Lifecycle

1. **Startup**: Pool created on application startup
2. **Acquisition**: Connections acquired from pool for queries
3. **Release**: Connections returned to pool after use
4. **Shutdown**: Pool closed on application shutdown

## Data Management

### Inserting Data

```python
# Individual message
await conn.execute("""
    INSERT INTO websocket_messages (
        timestamp, exchange, instrument, price, data, message_type
    ) VALUES ($1, $2, $3, $4, $5, $6)
""", timestamp, exchange, instrument, price, json.dumps(data), message_type)

# Batch insert
await conn.execute("""
    INSERT INTO websocket_batches (
        timestamp, exchange, total_messages, messages_per_second, messages
    ) VALUES ($1, $2, $3, $4, $5)
""", timestamp, exchange, count, mps, json.dumps(messages))
```

### Querying Data

```python
# Get recent messages
rows = await conn.fetch("""
    SELECT * FROM websocket_messages
    WHERE exchange = $1
    ORDER BY timestamp DESC
    LIMIT $2
""", exchange, limit)

# Count messages
count = await conn.fetchval("""
    SELECT COUNT(*) FROM websocket_messages
    WHERE exchange = $1
""", exchange)
```

### Common Queries

```sql
-- Recent messages
SELECT * FROM websocket_messages 
ORDER BY timestamp DESC 
LIMIT 100;

-- Messages by exchange
SELECT exchange, COUNT(*) as count 
FROM websocket_messages 
GROUP BY exchange;

-- Price history for instrument
SELECT timestamp, price 
FROM websocket_messages 
WHERE instrument = 'BTC-USDT'
ORDER BY timestamp DESC 
LIMIT 1000;

-- Connector data
SELECT * FROM api_connector_data 
WHERE connector_id = 'conn_abc'
ORDER BY timestamp DESC 
LIMIT 100;
```

## Performance Optimization

### Query Optimization

1. **Use Indexes**: Always query on indexed columns
2. **Limit Results**: Use LIMIT for large result sets
3. **Pagination**: Use OFFSET and LIMIT for pagination
4. **JSONB Queries**: Use JSONB operators for efficient JSON queries

### Index Usage

```sql
-- Efficient (uses index)
SELECT * FROM websocket_messages 
WHERE timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;

-- Efficient (uses composite index)
SELECT * FROM websocket_messages 
WHERE exchange = 'okx' AND instrument = 'BTC-USDT'
ORDER BY timestamp DESC;
```

### Maintenance

```sql
-- Analyze tables for query optimization
ANALYZE websocket_messages;
ANALYZE websocket_batches;

-- Vacuum to reclaim space
VACUUM ANALYZE websocket_messages;

-- Reindex if needed
REINDEX TABLE websocket_messages;
```

## Backup and Recovery

### Backup

```bash
# Full database backup
pg_dump -U postgres -d etl_tool > backup.sql

# Backup specific table
pg_dump -U postgres -d etl_tool -t websocket_messages > messages_backup.sql
```

### Restore

```bash
# Restore from backup
psql -U postgres -d etl_tool < backup.sql
```

### Automated Backups

Set up cron job (Linux) or Task Scheduler (Windows) for regular backups.

## Troubleshooting

### Connection Issues

**Error**: `connection refused`
- Check PostgreSQL service is running
- Verify port 5432 is accessible
- Check firewall settings

**Error**: `authentication failed`
- Verify username and password
- Check pg_hba.conf configuration
- Ensure user has proper permissions

### Performance Issues

**Slow Queries**:
- Check if indexes are being used: `EXPLAIN ANALYZE`
- Ensure proper indexes exist
- Consider partitioning large tables

**High Memory Usage**:
- Reduce connection pool size
- Implement data archiving
- Clean up old data regularly

### Data Issues

**Missing Data**:
- Check connector status
- Verify database connection
- Review error logs

**Duplicate Data**:
- Check for duplicate prevention logic
- Review message processing pipeline

## Monitoring

### Database Size

```sql
SELECT 
    pg_size_pretty(pg_database_size('etl_tool')) as database_size;

SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Table Statistics

```sql
-- Row counts
SELECT 
    'websocket_messages' as table_name, 
    COUNT(*) as row_count 
FROM websocket_messages
UNION ALL
SELECT 'websocket_batches', COUNT(*) FROM websocket_batches
UNION ALL
SELECT 'api_connector_data', COUNT(*) FROM api_connector_data;

-- Recent activity
SELECT 
    exchange,
    COUNT(*) as messages,
    MAX(timestamp) as last_message
FROM websocket_messages
GROUP BY exchange;
```

## Best Practices

1. **Regular Backups**: Schedule regular database backups
2. **Monitor Size**: Monitor database growth
3. **Index Maintenance**: Regularly analyze and reindex
4. **Connection Pooling**: Use connection pooling efficiently
5. **Data Archiving**: Archive old data to reduce table size
6. **Query Optimization**: Use EXPLAIN ANALYZE for slow queries
7. **Error Logging**: Monitor error logs regularly

---

**Last Updated**: 2024
**Version**: 1.0.0

