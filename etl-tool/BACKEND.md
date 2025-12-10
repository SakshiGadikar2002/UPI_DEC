# Backend Technical Documentation

Complete technical documentation for the ETL Tool backend server built with FastAPI.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Core Components](#core-components)
5. [Database Layer](#database-layer)
6. [API Endpoints](#api-endpoints)
7. [Job Scheduler](#job-scheduler)
8. [WebSocket Real-Time](#websocket-real-time)
9. [Connector System](#connector-system)
10. [Security](#security)
11. [Configuration](#configuration)
12. [Running the Server](#running-the-server)

## Architecture Overview

The backend is built using **FastAPI**, a modern, fast (high-performance) web framework for building APIs with Python 3.8+ based on standard Python type hints. The architecture follows a modular design pattern with clear separation of concerns.

### Key Design Principles

- **Async/Await**: Full asynchronous programming for high concurrency
- **Dependency Injection**: Clean separation of concerns
- **Type Safety**: Pydantic models for data validation
- **Connection Pooling**: Efficient database connection management
- **Event-Driven**: WebSocket support for real-time communication
- **Modular Design**: Components are loosely coupled and highly cohesive

## Technology Stack

### Backend Framework
- **FastAPI 0.100+** - Modern async web framework
- **Uvicorn** - ASGI server for production deployment
- **Pydantic** - Data validation using Python type hints

### Database
- **PostgreSQL 12+** - Primary data store
- **asyncpg** - Async PostgreSQL driver
- **psycopg2** - Synchronous PostgreSQL driver

### Job Scheduling
- **APScheduler 3.10+** - Task scheduling framework
- **ThreadPoolExecutor** - Concurrent API execution

### WebSocket & Real-Time
- **FastAPI WebSocket** - Native WebSocket support
- **asyncio** - Asynchronous I/O

### Utilities
- **requests** - HTTP client for APIs
- **cryptography** - Encryption for sensitive data
- **python-multipart** - File upload handling
- **cors** - Cross-Origin Resource Sharing support

## Project Structure

```
backend/
├── main.py                      # FastAPI application entry point
├── database.py                  # PostgreSQL connection and schema
├── requirements.txt             # Python dependencies
│
├── connectors/                  # API connector implementations
│   ├── __init__.py
│   ├── base_connector.py        # Abstract base class
│   ├── connector_factory.py     # Factory pattern for connectors
│   ├── rest_connector.py        # REST API connector
│   └── websocket_connector.py   # WebSocket connector
│
├── etl/                         # ETL pipeline components
│   ├── __init__.py
│   ├── extractor.py             # Data extraction logic
│   ├── transformer.py           # Data transformation
│   ├── loader.py                # Data loading to database
│   └── job_manager.py           # Job management
│
├── models/                      # Pydantic data models
│   ├── __init__.py
│   ├── connector.py             # Connector models
│   └── websocket_data.py        # WebSocket message models
│
├── services/                    # Business logic services
│   ├── __init__.py
│   ├── auth_handler.py          # Authentication logic
│   ├── connector_manager.py     # Connector management
│   ├── encryption.py            # Encryption/decryption
│   └── message_processor.py     # Message processing
│
├── job_scheduler/               # Scheduled API execution
│   ├── __init__.py
│   └── scheduler.py             # Job scheduler implementation
│
├── processed/                   # Processed data storage
├── uploads/                     # File upload storage
└── scripts/                     # Utility scripts
```

## Core Components

### 1. Main FastAPI Application (`main.py`)

The entry point that initializes:
- FastAPI app with CORS middleware
- PostgreSQL connection pool
- Job scheduler for automated API polling
- WebSocket endpoints for real-time data
- REST API endpoints for data operations

```python
app = FastAPI(
    title="ETL Tool API",
    description="Real-time data processing platform",
    version="1.0.0"
)

# CORS configuration for frontend access
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to DB, initialize scheduler
    await connect_to_postgres()
    initialize_scheduled_connectors()
    start_job_scheduler(...)
    
    yield
    
    # Shutdown: cleanup
    stop_job_scheduler()
    await close_postgres_connection()
```

### 2. Database Layer (`database.py`)

Handles PostgreSQL connections and schema:
- Connection pooling (asyncpg)
- Table creation and migrations
- Query execution
- Connection management

**Key Tables:**
- `api_connectors` - Connector configurations
- `api_connector_data` - API responses
- `websocket_data` - WebSocket messages
- `files` - Uploaded file metadata
- `file_data` - Parsed file contents

### 3. Connector System (`connectors/`)

Pluggable connector architecture:

- **BaseConnector**: Abstract base class defining interface
- **RestConnector**: For HTTP/HTTPS REST APIs
- **WebSocketConnector**: For WebSocket streams
- **ConnectorFactory**: Creates connectors based on type

### 4. ETL Pipeline (`etl/`)

Data processing pipeline:

- **Extractor**: Fetches data from sources
- **Transformer**: Applies transformations
- **Loader**: Saves to database
- **JobManager**: Orchestrates pipeline

### 5. Services (`services/`)

Business logic layer:

- **AuthHandler**: Manages authentication
- **EncryptionService**: Encrypts/decrypts sensitive data
- **ConnectorManager**: CRUD operations on connectors
- **MessageProcessor**: Processes WebSocket messages

### 6. Job Scheduler (`job_scheduler/`)

Automated API polling:

- Runs 8 APIs in parallel every 10 seconds
- ThreadPoolExecutor for concurrent execution
- Async callback to save results
- Graceful shutdown handling

## Database Layer

See [DATABASE.md](./DATABASE.md) for complete database documentation.

### Connection Pool

```python
# PostgreSQL connection pool
pool = await asyncpg.create_pool(
    host='localhost',
    port=5432,
    user='postgres',
    password='1972',
    database='etl_tool',
    min_size=5,
    max_size=20
)
```

### Key Tables

```sql
-- API Connectors Configuration
CREATE TABLE api_connectors (
    id SERIAL PRIMARY KEY,
    connector_id VARCHAR(255) UNIQUE NOT NULL,
    connector_name TEXT,
    source_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API Response Data
CREATE TABLE api_connector_data (
    id SERIAL PRIMARY KEY,
    connector_id VARCHAR(255) REFERENCES api_connectors(connector_id),
    response_data JSONB NOT NULL,
    raw_response TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- WebSocket Real-Time Data
CREATE TABLE websocket_data (
    id SERIAL PRIMARY KEY,
    message_type VARCHAR(100),
    data JSONB NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoints

### Health & Status
```
GET /                       # Health check
GET /api/status            # Server status
```

### WebSocket
```
WS /ws                     # Real-time data stream
POST /ws/test             # Test WebSocket broadcast
```

### Connectors
```
GET /api/connectors        # List all connectors
POST /api/connectors       # Create connector
GET /api/connectors/{id}   # Get connector details
PUT /api/connectors/{id}   # Update connector
DELETE /api/connectors/{id} # Delete connector
GET /api/connectors/{id}/status # Connector status
```

### Data Operations
```
GET /api/data/                           # Get all aggregate data
GET /api/data/{connector_id}             # Get aggregate data by connector
GET /api/data/items                      # Get all granular items [NEW]
GET /api/data/items/{connector_id}       # Get items by connector [NEW]
GET /api/data/items/symbol/{symbol}      # Get items by coin symbol [NEW]
POST /api/data/extract                   # Extract from URL
POST /api/data/upload                    # Upload file
GET /api/data/{connector_id}/latest      # Latest aggregate data
GET /api/data/{connector_id}/items/latest # Latest items [NEW]
```

### New Granular Data Endpoints [NEW]

```
GET /api/data/items
    Query Parameters:
    - limit (default: 100)
    - offset (default: 0)
    - connector_id (optional filter)
    - symbol (optional coin symbol filter)
    - order (default: timestamp DESC)
    
    Response:
    {
        "items": [
            {
                "connector_id": "binance_24hr",
                "api_name": "Binance - 24hr Ticker",
                "coin_symbol": "BTC",
                "coin_name": "Bitcoin",
                "price": 95000.50,
                "market_cap": 1900000000000,
                "volume_24h": 45000000000,
                "price_change_24h": 2.5,
                "market_cap_rank": 1,
                "timestamp": "2025-12-08T16:00:00Z"
            },
            ...
        ],
        "total": 3000,
        "limit": 100,
        "offset": 0
    }

GET /api/data/items/{connector_id}
    Returns granular items for specific API connector

GET /api/data/items/symbol/{symbol}
    Returns all items with matching coin symbol
```

### Item Data Structure

```json
{
    "id": 1972,
    "connector_id": "binance_24hr",
    "api_name": "Binance - 24hr Ticker",
    "exchange": "binance",
    "coin_name": "Bitcoin",
    "coin_symbol": "BTC",
    "price": 95000.50,
    "market_cap": 1900000000000,
    "volume_24h": 45000000000,
    "price_change_24h": 2.5,
    "market_cap_rank": 1,
    "timestamp": "2025-12-08T16:00:00Z",
    "response_time_ms": 145
}
```


### File Processing
```
POST /api/process/csv    # Process CSV file
POST /api/process/json   # Process JSON file
```

## Job Scheduler

See [JOB_SCHEDULING.md](./JOB_SCHEDULING.md) for complete scheduler documentation.

### Scheduled APIs

The scheduler automatically executes these 8 APIs every 10 seconds in parallel:

1. **Binance - Order Book** (`binance_orderbook`)
2. **Binance - Prices** (`binance_prices`)
3. **Binance - 24h Ticker** (`binance_24hr`)
4. **CoinGecko - Global** (`coingecko_global`)
5. **CoinGecko - Top** (`coingecko_top`)
6. **CoinGecko - Trending** (`coingecko_trending`)
7. **CryptoCompare - Multi Price** (`cryptocompare_multi`)
8. **CryptoCompare - Top** (`cryptocompare_top`)

### Configuration

```python
# In job_scheduler/scheduler.py

SCHEDULE_INTERVAL_SECONDS = 10  # Run every 10 seconds
MAX_WORKERS = 8                 # 8 concurrent requests
```

### Performance

- **Throughput**: 48-100+ requests/minute
- **Latency**: 200-2000ms per API
- **Memory**: ~20-50MB per worker
- **Concurrency**: 8 parallel requests

## WebSocket Real-Time

See [WEBSOCKET_REALTIME.md](./WEBSOCKET_REALTIME.md) for complete WebSocket documentation.

### Connection

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Process and broadcast
            await broadcast_to_clients(data)
    except WebSocketDisconnect:
        # Client disconnected
        pass
```

### Message Format

```json
{
    "type": "price_update",
    "connector_id": "binance_prices",
    "data": {...},
    "timestamp": "2025-12-08T16:00:00Z"
}
```

## Connector System

### Creating a Connector

```python
# REST Connector Example
from connectors.rest_connector import RestConnector

connector = RestConnector(
    id="my_api",
    name="My Custom API",
    url="https://api.example.com/data",
    method="GET",
    auth_type="api_key",
    auth_value="your-api-key"
)

# Save to database
response = await connector.save()
```

### Authentication Types

- **None**: No authentication
- **API Key**: Header-based API key
- **Bearer Token**: JWT or OAuth tokens
- **Basic Auth**: Username/password
- **HMAC**: Signed requests (Binance, etc.)

## Security

### Encryption

API keys and secrets are encrypted using AES-256:

```python
from services.encryption import EncryptionService

encryption = EncryptionService()
encrypted = encryption.encrypt(api_key)
decrypted = encryption.decrypt(encrypted)
```

### CORS

Configured for frontend access:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Input Validation

All inputs validated using Pydantic models:

```python
from pydantic import BaseModel, Field

class ConnectorCreate(BaseModel):
    connector_id: str = Field(..., min_length=1)
    connector_name: str
    url: str
    method: str = "GET"
```

### SQL Injection Protection

All queries use parameterized statements:

```python
# Safe - parameterized query
await conn.execute(
    "SELECT * FROM api_connectors WHERE connector_id = $1",
    connector_id
)
```

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://postgres:1972@localhost:5432/etl_tool

# Encryption
ENCRYPTION_KEY=your-secret-key-32-chars-long

# Server
DEBUG=False
WORKERS=4

# API Keys (optional)
BINANCE_API_KEY=...
COINGECKO_API_KEY=...
```

### PostgreSQL Setup

```bash
# Create database
createdb etl_tool

# Create user
createuser postgres

# Set password
psql -U postgres -c "ALTER USER postgres WITH PASSWORD '1972';"
```

## Running the Server

### Development

```bash
# With auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# With logs
uvicorn main:app --reload --log-level debug
```

### Production

```bash
# With Gunicorn (4 workers)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000

# Or direct with Uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Health Check

```bash
curl http://localhost:8000/
# Response: 200 OK with status info
```

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Logging

Logs are configured with INFO level by default:

```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Server started")
logger.error("Database error", exc_info=True)
```

## Performance Tuning

### Connection Pool

```python
# Increase pool size for high load
min_size=10      # Minimum connections
max_size=50      # Maximum connections
max_cached_statement_lifetime=300  # Cache statements
max_cacheable_statement_size=15000
```

### Query Optimization

```sql
-- Add indexes for common queries
CREATE INDEX idx_connector_id ON api_connector_data(connector_id);
CREATE INDEX idx_timestamp ON api_connector_data(timestamp DESC);
```

## Troubleshooting

### Database Connection Failed

```bash
# Test PostgreSQL connection
psql -U postgres -d etl_tool
```

### Port Already in Use

```bash
# Use different port
uvicorn main:app --port 8001
```

### Event Loop Issues

```bash
# Ensure asyncio is properly closed
# This is handled automatically by FastAPI
```

---

**Last Updated**: December 9, 2025  
**Version**: 1.0.0
