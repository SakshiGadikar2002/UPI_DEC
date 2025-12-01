# Backend Technical Documentation

Complete technical documentation for the ETL Tool backend server.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Core Components](#core-components)
5. [Database Layer](#database-layer)
6. [API Endpoints](#api-endpoints)
7. [Connector System](#connector-system)
8. [Message Processing](#message-processing)
9. [Security](#security)
10. [Configuration](#configuration)
11. [Deployment](#deployment)
12. [Testing](#testing)

## Architecture Overview

The backend is built using **FastAPI**, a modern, fast (high-performance) web framework for building APIs with Python 3.8+ based on standard Python type hints. The architecture follows a modular design pattern with clear separation of concerns.

### Key Design Principles

- **Async/Await**: Full asynchronous programming for high concurrency
- **Dependency Injection**: Clean separation of concerns
- **Type Safety**: Pydantic models for data validation
- **Connection Pooling**: Efficient database connection management
- **Event-Driven**: WebSocket support for real-time communication

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                   │
│                      (main.py)                          │
└──────────────┬──────────────────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────────┐    ┌───────▼────────┐
│  REST API  │    │  WebSocket API │
│ Endpoints  │    │   Endpoints    │
└───┬────────┘    └───────┬────────┘
    │                     │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  Connector Manager  │
    │  (connector_manager)│
    └──────────┬──────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────────┐    ┌───────▼────────┐
│ REST       │    │  WebSocket     │
│ Connector  │    │  Connector     │
└───┬────────┘    └───────┬────────┘
    │                     │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │ Message Processor   │
    └──────────┬──────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────────┐    ┌───────▼────────┐
│ PostgreSQL │    │  WebSocket     │
│  Database  │    │   Broadcast    │
└────────────┘    └────────────────┘
```

## Technology Stack

### Core Framework
- **FastAPI 0.104.1**: Modern, fast web framework
- **Uvicorn 0.24.0**: ASGI server implementation
- **Python 3.8+**: Programming language

### Database
- **asyncpg 0.29.0**: Async PostgreSQL driver
- **psycopg2-binary 2.9.9**: PostgreSQL adapter (for database creation)
- **PostgreSQL 17+**: Database server

### Data Processing
- **Pydantic 2.5.0**: Data validation using Python type annotations
- **Pandas 2.1.3**: Data manipulation and analysis

### Networking
- **aiohttp 3.9.1**: Async HTTP client/server
- **websockets 15.0.1**: WebSocket implementation
- **requests 2.31.0**: HTTP library

### Security
- **cryptography 41.0.7**: Encryption library

## Project Structure

```
backend/
├── main.py                 # FastAPI application entry point
├── database.py             # PostgreSQL connection and schema
├── requirements.txt        # Python dependencies
│
├── connectors/             # Data source connectors
│   ├── __init__.py
│   ├── base_connector.py   # Abstract base connector
│   ├── connector_factory.py # Connector factory
│   ├── rest_connector.py  # REST API connector
│   └── websocket_connector.py # WebSocket connector
│
├── etl/                    # ETL pipeline components
│   ├── __init__.py
│   ├── extractor.py       # Data extraction
│   ├── transformer.py     # Data transformation
│   ├── loader.py          # Data loading
│   └── job_manager.py     # Job management
│
├── models/                 # Pydantic data models
│   ├── connector.py       # Connector models
│   └── websocket_data.py  # WebSocket data models
│
├── services/               # Business logic services
│   ├── __init__.py
│   ├── auth_handler.py    # Authentication handlers
│   ├── connector_manager.py # Connector lifecycle management
│   ├── encryption.py      # Encryption service
│   └── message_processor.py # Message processing
│
└── tests/                  # Test files
    ├── test_postgres_connection.py
    └── verify_setup.py
```

## Core Components

### 1. Main Application (`main.py`)

The main FastAPI application that orchestrates all components.

#### Key Features
- **Lifespan Management**: Handles startup and shutdown events
- **CORS Middleware**: Cross-origin resource sharing configuration
- **Connection Manager**: Manages WebSocket connections for real-time updates
- **API Routes**: RESTful API endpoints for all operations

#### Application Lifecycle

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to PostgreSQL
    await connect_to_postgres()
    yield
    # Shutdown: Close PostgreSQL connection
    await close_postgres_connection()
```

### 2. Database Layer (`database.py`)

Handles all PostgreSQL operations including connection pooling and schema management.

#### Connection Pooling
- **Min Size**: 5 connections
- **Max Size**: 20 connections
- **Timeout**: 10 seconds

#### Database Schema
See [POSTGRESQL_SETUP.md](./POSTGRESQL_SETUP.md) for complete schema documentation.

### 3. Connector System

#### Base Connector (`connectors/base_connector.py`)
Abstract base class defining the connector interface.

**Key Methods**:
- `connect()`: Establish connection
- `disconnect()`: Close connection
- `start()`: Start data collection
- `stop()`: Stop data collection
- `get_status()`: Get current status

#### REST Connector (`connectors/rest_connector.py`)
Polls REST APIs at configurable intervals.

**Features**:
- Configurable polling intervals
- Multiple authentication methods
- Custom headers and query parameters
- Error handling and retry logic

#### WebSocket Connector (`connectors/websocket_connector.py`)
Maintains persistent WebSocket connections.

**Features**:
- Auto-reconnection with exponential backoff
- Ping/pong keepalive
- Message buffering
- Connection health monitoring

#### Connector Factory (`connectors/connector_factory.py`)
Automatically detects protocol and exchange type.

**Detection Logic**:
- Protocol: Checks URL scheme (http/https vs ws/wss)
- Exchange: Parses URL to identify exchange (OKX, Binance, etc.)

### 4. Message Processing (`services/message_processor.py`)

Transforms and routes incoming messages.

#### Processing Pipeline
1. **Normalization**: Convert exchange-specific formats to standard format
2. **Extraction**: Extract instrument, price, and metadata
3. **Database Save**: Persist to PostgreSQL
4. **WebSocket Broadcast**: Send to connected clients

#### Supported Exchange Formats
- **OKX**: `{arg: {...}, data: [...]}`
- **Binance**: `{stream: "...", data: {...}}` or direct trade format
- **Custom**: Generic JSON object handling

### 5. Connector Manager (`services/connector_manager.py`)

Manages the lifecycle of all connectors.

**Responsibilities**:
- Create and register connectors
- Start/stop connectors
- Track connector status
- Handle errors and reconnections
- Update database status

### 6. Encryption Service (`services/encryption.py`)

Securely encrypts sensitive data before storage.

**Encryption**:
- Algorithm: AES-256
- Key Management: Environment variable (ENCRYPTION_KEY)
- Data Encrypted: API keys, secrets, headers, query parameters

### 7. Authentication Handlers (`services/auth_handler.py`)

Handles various authentication methods.

**Supported Methods**:
- **API Key**: Simple API key in headers
- **Bearer Token**: OAuth2-style bearer tokens
- **HMAC**: HMAC-SHA256 signature generation
- **Basic Auth**: HTTP Basic Authentication

## Database Layer

### Connection Management

```python
# Connection pool configuration
pool = await asyncpg.create_pool(
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    database=POSTGRES_DB,
    min_size=5,
    max_size=20,
    timeout=10
)
```

### Tables

1. **websocket_messages**: Individual real-time messages
2. **websocket_batches**: Batched messages with metrics
4. **api_connectors**: Connector configurations
5. **connector_status**: Runtime status tracking
6. **api_connector_data**: Data from API connectors

See [POSTGRESQL_SETUP.md](./POSTGRESQL_SETUP.md) for detailed schema.

## API Endpoints

### WebSocket Data Endpoints

#### `POST /api/websocket/save`
Save individual WebSocket message to database.

**Request Body**:
```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "exchange": "okx",
  "type": "trade",
  "data": {...},
  "messageNumber": 1,
  "format": "OKX"
}
```

#### `POST /api/websocket/save-batch`
Save batch of messages with metrics.

#### `GET /api/websocket/data`
Retrieve WebSocket data with pagination.

**Query Parameters**:
- `exchange`: Filter by exchange
- `instrument`: Filter by instrument
- `limit`: Number of records (max 100,000)
- `skip`: Offset for pagination
- `collection_type`: "messages" or "batches"
- `sort_by`: Field to sort by
- `sort_order`: -1 (desc) or 1 (asc)

#### `GET /api/websocket/data/count`
Get total count of messages.

### Connector Management Endpoints

#### `POST /api/connectors`
Create new API connector.

**Request Body**:
```json
{
  "name": "Binance BTC Price",
  "api_url": "https://api.binance.com/api/v3/ticker/price",
  "http_method": "GET",
  "headers": {},
  "query_params": {"symbol": "BTCUSDT"},
  "auth_type": "None",
  "polling_interval": 1000
}
```

#### `GET /api/connectors`
List all connectors.

#### `GET /api/connectors/{connector_id}`
Get connector details.

#### `PUT /api/connectors/{connector_id}`
Update connector configuration.

#### `DELETE /api/connectors/{connector_id}`
Delete connector.

#### `POST /api/connectors/{connector_id}/start`
Start connector (begins data collection).

#### `POST /api/connectors/{connector_id}/stop`
Stop connector.

#### `GET /api/connectors/{connector_id}/status`
Get connector runtime status.

#### `GET /api/connectors/{connector_id}/data`
Get data collected by connector.

**Query Parameters**:
- `limit`: Number of records (max 10,000)
- `skip`: Offset
- `sort_by`: Field to sort by
- `sort_order`: -1 (desc) or 1 (asc)

### Database Endpoints

#### `GET /api/postgres/status`
Check PostgreSQL connection status and table counts.

**Response**:
```json
{
  "status": "connected",
  "database": "etl_tool",
            "tables": {
                "websocket_batches": 8131,
                "websocket_messages": 879089
            }
}
```

### Real-Time WebSocket

#### `WebSocket /api/realtime`
WebSocket endpoint for real-time data updates to frontend.

**Message Format**:
```json
{
  "type": "data_update",
  "id": 12345,
  "source_id": "abc123",
  "session_id": "conn_xyz",
  "connector_id": "conn_abc",
  "timestamp": "2024-01-01T00:00:00Z",
  "exchange": "okx",
  "instrument": "BTC-USDT",
  "price": 50000.50,
  "data": {...}
}
```

## Connector System

### Creating a Connector

```python
# Via API
POST /api/connectors
{
  "name": "My Connector",
  "api_url": "https://api.example.com/data",
  "http_method": "GET",
  "auth_type": "API_KEY",
  "api_key": "your_key",
  "polling_interval": 5000
}
```

### Connector Lifecycle

1. **Create**: Connector configuration saved to database
2. **Start**: Connector instance created and started
3. **Running**: Collecting data and processing messages
4. **Stop**: Connector stopped, resources cleaned up
5. **Delete**: Connector removed from database

### Connector Status

Status values:
- `inactive`: Created but not started
- `running`: Actively collecting data
- `stopped`: Manually stopped
- `error`: Error occurred

## Message Processing

### Processing Flow

```
Raw Message → Normalize → Extract Fields → Save to DB → Broadcast to WS
```

### Normalization

Converts exchange-specific formats to standard format:

```python
{
  "connector_id": "conn_abc",
  "timestamp": "2024-01-01T00:00:00Z",
  "exchange": "okx",
  "instrument": "BTC-USDT",
  "price": 50000.50,
  "data": {...},
  "message_type": "trade",
  "status_code": 200,
  "response_time_ms": 150.5
}
```

## Security

### Encryption

All sensitive data is encrypted using AES-256:

- API keys
- API secrets
- Bearer tokens
- Custom headers
- Query parameters

**Key Management**:
```bash
export ENCRYPTION_KEY="your-32-character-encryption-key"
```

### Authentication

Supported authentication methods:
1. **None**: No authentication
2. **API Key**: Simple key in headers
3. **Bearer Token**: OAuth2-style tokens
4. **HMAC**: HMAC-SHA256 signatures
5. **Basic Auth**: HTTP Basic Authentication

## Configuration

### Environment Variables

```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=etl_tool

# Encryption
ENCRYPTION_KEY=your-32-character-key

# CORS (configured in code)
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Default Configuration

- **Database**: `etl_tool` on `localhost:5432`
- **API Port**: `8000`
- **Connection Pool**: 5-20 connections
- **CORS Origins**: localhost:3000, localhost:5173, localhost:5174

## Deployment

### Development

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production

```bash
# Using Gunicorn with Uvicorn workers
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Or using Uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker (Example)

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Testing

### Connection Tests

```bash
# Test PostgreSQL connection
python test_postgres_connection.py

# Verify complete setup
python verify_setup.py
```

### Manual Testing

1. **API Documentation**: http://localhost:8000/docs
2. **Health Check**: http://localhost:8000/api/postgres/status
3. **Test WebSocket**: Use `/api/realtime/test` endpoint

## Performance Considerations

### Database Optimization
- Connection pooling (5-20 connections)
- Indexed queries for fast lookups
- Batch inserts for high throughput
- JSONB for flexible data storage

### Memory Management
- Message buffering with size limits
- Automatic cleanup of old data
- Efficient connection reuse

### Scalability
- Async/await for high concurrency
- Connection pooling for database
- WebSocket connection management
- Horizontal scaling support

## Error Handling

### Database Errors
- Connection retry logic
- Graceful degradation
- Error logging

### Connector Errors
- Auto-reconnection with exponential backoff
- Error status tracking
- Error logs in database

### API Errors
- HTTP status codes
- Detailed error messages
- Validation errors

## Logging

Logging is configured using Python's `logging` module:

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Message")
logger.error("Error message")
```

Log levels:
- **INFO**: General information
- **ERROR**: Error messages
- **DEBUG**: Detailed debugging (development)

## Best Practices

1. **Always use connection pooling** for database operations
2. **Encrypt sensitive data** before storage
3. **Validate input** using Pydantic models
4. **Handle errors gracefully** with proper error messages
5. **Use async/await** for I/O operations
6. **Monitor connector status** regularly
7. **Clean up resources** on shutdown

## Troubleshooting

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for common issues and solutions.

---

**Last Updated**: 2024
**Version**: 1.0.0

