# Job Scheduling Documentation

Complete guide to the automated job scheduler for parallel API execution.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Scheduled APIs](#scheduled-apis)
4. [Configuration](#configuration)
5. [Performance](#performance)
6. [Monitoring](#monitoring)
7. [Adding Custom APIs](#adding-custom-apis)
8. [Troubleshooting](#troubleshooting)

## Overview

The job scheduler automatically executes multiple APIs in parallel at fixed intervals. It uses:
- **APScheduler** for scheduling
- **ThreadPoolExecutor** for concurrent execution
- **Async callbacks** to save results to database
- **Event loop** integration for FastAPI

### Key Features

✅ 8 APIs in parallel every 10 seconds  
✅ Automatic database persistence  
✅ Graceful error handling  
✅ Activity timestamp updates  
✅ Thread-safe execution  
✅ Zero manual intervention required  

## Architecture

### Components

```
┌─────────────────────────────────────┐
│  FastAPI App (main.py)              │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ Job Scheduler               │   │
│  │                             │   │
│  │ ┌───────────────────────┐  │   │
│  │ │ APScheduler           │  │   │
│  │ │ (Timing & Triggers)   │  │   │
│  │ └───────────────────────┘  │   │
│  │ ┌───────────────────────┐  │   │
│  │ │ ThreadPoolExecutor    │  │   │
│  │ │ (8 workers)           │  │   │
│  │ └───────────────────────┘  │   │
│  │                             │   │
│  │ ┌───────────────────────┐  │   │
│  │ │ SCHEDULED_APIS (8)    │  │   │
│  │ │ • Binance (3)         │  │   │
│  │ │ • CoinGecko (3)       │  │   │
│  │ │ • CryptoCompare (2)   │  │   │
│  │ └───────────────────────┘  │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ save_to_database()          │   │
│  │ (Async Callback)            │   │
│  │ ↓ INSERT INTO api_connector_│   │
│  │   data                      │   │
│  │ ↓ UPDATE api_connectors     │   │
│  │   SET updated_at = NOW()    │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
        ↓
    ┌───────────────┐
    │  PostgreSQL   │
    │  Database     │
    └───────────────┘
```

### Execution Flow

1. **Startup** (Backend Start)
   - Initialize `JobScheduler` instance with TWO callbacks:
     - `save_to_database` - saves aggregate API response
     - `save_api_items_to_database` - saves individual items from response
   - Create ThreadPoolExecutor with 8 workers
   - Schedule first batch immediately
   - Register repeating schedule every 10s

2. **Each Interval** (Every 10 seconds)
   - `_run_scheduled_batch()` called
   - Submit 8 API calls to executor
   - All 8 execute in parallel (non-blocking)
   - Each API has timeout of 15 seconds

3. **API Execution** (In Worker Thread)
   - Make HTTP request
   - Parse response
   - Create message dict with metadata
   - **Invoke TWO callbacks** (not one):
     - `save_to_database()` for aggregate data
     - `save_api_items_to_database()` for individual items

4. **Database Save - Aggregate** (Async)
   - INSERT into `api_connector_data` (1 row per API call)
   - Stores entire response as JSON
   - UPDATE `api_connectors.updated_at`

5. **Database Save - Granular** (Async)
   - Extract individual items from response
   - INSERT into `api_connector_items` (100-1000s of rows per API call)
   - Parse different API response formats:
     - **CoinGecko**: Extract coin array → individual rows
     - **Binance**: Extract trading pairs/prices → individual rows
     - **CryptoCompare**: Extract symbol data → individual rows
   - Handle errors gracefully
   - Log results

6. **Shutdown** (Backend Stop)
   - Stop accepting new jobs
   - Wait for in-flight requests
   - Shutdown executor gracefully
   - Close database connections

### Dual-Callback Architecture

The job scheduler now uses **TWO callbacks** for data persistence:

```python
# Callback 1: Aggregate Data (Original)
save_to_database(connector_id, api_name, response_data, response_time_ms)
├─ Purpose: Store complete API response as JSON blob
├─ Destination: api_connector_data table
└─ Volume: 1 row per 10-second interval

# Callback 2: Granular Items (NEW)
save_api_items_to_database(connector_id, api_name, response_data, response_time_ms)
├─ Purpose: Extract and store individual items
├─ Destination: api_connector_items table
├─ Volume: 100-1000+ rows per 10-second interval
└─ Logic: Parse 8 different API response formats
```

### Item Extraction Logic

For each API, items are extracted from different response structures:

| API | Response Format | Items Per Call | Example |
|-----|-----------------|----------------|---------|
| Binance 24hr | Array of 1000+ objects | ~1000+ | Trading pairs with OHLCV |
| Binance Prices | Array of all symbols | ~1400+ | Symbol + Price |
| CoinGecko Top | Array of 100 coins | ~100 | Coins with price/market cap |
| CoinGecko Trending | Array of trending | ~7-20 | Top trending coins |
| CoinGecko Global | Single object metrics | ~5 | Global stats extracted |
| CryptoCompare Multi | Symbol object keys | ~10 | BTC, ETH, BNB prices |
| CryptoCompare Top | Array of 10 coins | ~10 | Top coins with data |

**Total Data Points Per 10 Seconds:** 3,000+ items across all APIs


    },
    {
        "id": "coingecko_top",
        "name": "CoinGecko - Top Cryptocurrencies",
        "url": "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100",
        "method": "GET"
    },
    {
        "id": "coingecko_trending",
        "name": "CoinGecko - Trending Coins",
        "url": "https://api.coingecko.com/api/v3/search/trending",
        "method": "GET"
    },
    {
        "id": "cryptocompare_multi",
        "name": "CryptoCompare - Multi Price",
        "url": "https://min-api.cryptocompare.com/data/pricemulti?fsyms=BTC,ETH,BNB&tsyms=USD",
        "method": "GET"
    },
    {
        "id": "cryptocompare_top",
        "name": "CryptoCompare - Top Coins",
        "url": "https://min-api.cryptocompare.com/data/top/mktcapfull?limit=10&tsym=USD",
        "method": "GET"
    }
]
```

### API Details

| API | Source | Endpoint | Response Time |
|-----|--------|----------|---------------|
| Order Book | Binance | /api/v3/depth | 250-350ms |
| Prices | Binance | /api/v3/ticker/price | 250-350ms |
| 24hr Ticker | Binance | /api/v3/ticker/24hr | 350-450ms |
| Global | CoinGecko | /api/v3/global | 400-800ms |
| Top | CoinGecko | /api/v3/coins/markets | 400-1000ms |
| Trending | CoinGecko | /api/v3/search/trending | 150-300ms |
| Multi Price | CryptoCompare | /data/pricemulti | 600-1500ms |
| Top Coins | CryptoCompare | /data/top/mktcapfull | 600-1500ms |

## Configuration

### Scheduler Settings

Edit `backend/job_scheduler/scheduler.py`:

```python
# Schedule interval in seconds
SCHEDULE_INTERVAL_SECONDS = 10

# Max concurrent workers
MAX_WORKERS = 8

# Request timeout
REQUEST_TIMEOUT = 15  # seconds

# Number of APIs
NUM_APIS = 8
```

### Adjusting Interval

```python
# Run every 5 seconds (faster)
SCHEDULE_INTERVAL_SECONDS = 5

# Run every 30 seconds (slower)
SCHEDULE_INTERVAL_SECONDS = 30

# Run every minute
SCHEDULE_INTERVAL_SECONDS = 60
```

### Adjusting Workers

```python
# For 16 APIs
MAX_WORKERS = 16

# For 32 APIs
MAX_WORKERS = 32

# For high-concurrency
MAX_WORKERS = 64
```

### Timeout Configuration

```python
# Increase timeout for slow APIs
REQUEST_TIMEOUT = 30  # 30 seconds

# Decrease for faster fail-over
REQUEST_TIMEOUT = 5   # 5 seconds
```

## Performance

### Throughput

With 8 APIs and 10-second interval:

```
Requests per minute = (8 APIs / 10 seconds) × 60
                    = 48 requests/minute
                    = 2,880 requests/hour
                    = 69,120 requests/day
```

### Scaling

| Config | APIs | Workers | Interval | Requests/Min |
|--------|------|---------|----------|--------------|
| Small | 8 | 8 | 10s | 48 |
| Medium | 16 | 16 | 10s | 96 |
| Large | 32 | 32 | 10s | 192 |
| High-Volume | 50 | 50 | 5s | 600 |

### Response Times

**Total batch execution time** = Max API response time + overhead

```
Batch Execution = MAX(api1_time, api2_time, ..., api8_time) + 50ms

Example:
- Fastest API: 150ms (CoinGecko Trending)
- Slowest API: 1500ms (CryptoCompare)
- Overhead: 50ms
- Total: 1500ms + 50ms = 1550ms (well under 10s interval)
```

### Memory Usage

Per scheduler:
- ThreadPoolExecutor: ~50MB (8 workers)
- Queue buffers: ~10MB
- Total: ~60MB

Per worker thread:
- ~20-30MB per concurrent request

### Database Impact

Per 24 hours (with 8 APIs @ 10s interval):

```
Rows inserted: 48 requests/min × 60 min × 24 hours = 69,120 rows/day
Data size: ~69K rows × 5KB average = ~345MB/day
Database growth: ~10GB/month
```

## Monitoring

### Logs

Monitor scheduler execution:

```bash
# View live logs
tail -f backend.log | grep "JOB"

# Filter for specific API
tail -f backend.log | grep "binance_orderbook"

# Show errors only
tail -f backend.log | grep "ERROR"
```

### Log Format

```
INFO:job_scheduler.scheduler:[JOB] Running batch of 8 APIs in parallel...
INFO:job_scheduler.scheduler:[JOB] Executing: Binance - Order Book -> https://...
INFO:job_scheduler.scheduler:[JOB] Saved result: Binance - Order Book (200) in 283ms
```

### Database Queries

**Check execution rate:**
```sql
-- Count records per minute from last hour
SELECT DATE_TRUNC('minute', timestamp) as minute,
       COUNT(*) as count
FROM api_connector_data
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY minute
ORDER BY minute DESC;
```

**Monitor by connector:**
```sql
-- Latest timestamp for each connector
SELECT connector_id, MAX(timestamp) as last_update,
       COUNT(*) as total_records
FROM api_connector_data
GROUP BY connector_id
ORDER BY last_update DESC;
```

**Check response times:**
```sql
-- Average response time by API
SELECT connector_id,
       AVG(response_time_ms) as avg_ms,
       MIN(response_time_ms) as min_ms,
       MAX(response_time_ms) as max_ms,
       COUNT(*) as samples
FROM api_connector_data
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY connector_id
ORDER BY avg_ms DESC;
```

### Health Check

```bash
# Is scheduler running?
curl http://localhost:8000/

# Check latest data
curl http://localhost:8000/api/data/binance_prices
```

## Adding Custom APIs

### Quick Guide

1. **Edit scheduler configuration:**
   ```bash
   nano backend/job_scheduler/scheduler.py
   ```

2. **Add to SCHEDULED_APIS list:**
   ```python
   {
       "id": "my_custom_api",
       "name": "My Custom API Name",
       "url": "https://api.example.com/endpoint",
       "method": "GET"
   }
   ```

3. **Increase workers if needed:**
   ```python
   MAX_WORKERS = 16  # For 15+ APIs
   ```

4. **Restart backend:**
   ```bash
   # Kill current process
   pkill -f "uvicorn main"
   
   # Restart
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

### Example: Add Weather API

```python
{
    "id": "weather_london",
    "name": "London Weather - Temperature",
    "url": "https://api.open-meteo.com/v1/forecast?latitude=51.5074&longitude=-0.1278&current=temperature_2m",
    "method": "GET"
}
```

### Example: Add with Authentication

```python
{
    "id": "my_protected_api",
    "name": "My Protected API",
    "url": "https://api.example.com/secure",
    "method": "GET",
    "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE",
        "X-API-Key": "your-api-key"
    }
}
```

See [ADD_CUSTOM_APIS.md](./backend/ADD_CUSTOM_APIS.md) for complete guide.

## Troubleshooting

### Scheduler Not Running

**Check logs:**
```bash
tail -f backend.log | grep "JOB"
```

**Restart scheduler:**
```python
# In backend terminal
# Kill and restart backend process
pkill -f "uvicorn main"
uvicorn main:app --host 0.0.0.0 --port 8000
```

### API Failing

**Check response:**
```bash
# Test API manually
curl "https://api.binance.com/api/v3/depth?symbol=BTCUSDT" | jq
```

**Database errors:**
```sql
SELECT * FROM api_connector_data 
WHERE connector_id = 'binance_orderbook'
  AND status_code NOT IN (200, 201)
ORDER BY timestamp DESC;
```

### High Response Times

**Identify slow APIs:**
```sql
SELECT connector_id, AVG(response_time_ms) as avg
FROM api_connector_data
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY connector_id
ORDER BY avg DESC;
```

**Possible solutions:**
- Increase timeout: `REQUEST_TIMEOUT = 30`
- Check network connectivity
- Check API provider status
- Reduce request frequency: `SCHEDULE_INTERVAL_SECONDS = 20`

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -U postgres -d etl_tool

# Check pool status
SELECT count(*) as connection_count FROM pg_stat_activity;
```

---

**Last Updated**: December 8, 2025  
**Version**: 1.0.0
