# Backend Technical Deep Dive

Comprehensive technical documentation covering all aspects of the backend implementation.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Database Design](#database-design)
3. [API Design](#api-design)
4. [Connector Architecture](#connector-architecture)
5. [Message Processing Pipeline](#message-processing-pipeline)
6. [Security Implementation](#security-implementation)
7. [Performance Optimization](#performance-optimization)
8. [Error Handling](#error-handling)
9. [Testing Strategy](#testing-strategy)
10. [Deployment Architecture](#deployment-architecture)

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Layer                             │
│              (React Frontend / API Clients)                  │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP/WebSocket
┌───────────────────────▼─────────────────────────────────────┐
│                    API Gateway Layer                         │
│                      (FastAPI)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ REST API     │  │ WebSocket    │  │  WebSocket   │       │
│  │ Endpoints    │  │ API          │  │  Broadcast   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
┌───────▼────────┐            ┌─────────▼────────┐
│  Connector     │            │  Message        │
│  Manager       │            │  Processor       │
└───────┬────────┘            └─────────┬────────┘
        │                               │
┌───────▼────────┐            ┌─────────▼────────┐
│  Connectors    │            │  Database        │
│  (REST/WS)     │            │  Layer           │
└───────┬────────┘            └─────────┬────────┘
        │                               │
        └───────────────┬───────────────┘
                        │
                ┌───────▼────────┐
                │  PostgreSQL    │
                │  Database      │
                └────────────────┘
```

### Component Interaction Flow

1. **Client Request** → FastAPI receives HTTP/WebSocket request
2. **Route Handler** → Processes request and calls appropriate service
3. **Service Layer** → Business logic execution
4. **Connector/Processor** → Data processing or connector management
5. **Database** → Data persistence
6. **Response** → Return result to client

## Database Design

### Entity Relationship Diagram

```
api_connectors (1) ──< (N) connector_status
api_connectors (1) ──< (N) api_connector_data
websocket_messages (standalone)
websocket_batches (standalone)
```

### Table Relationships

- **api_connectors** → **connector_status**: One-to-One (via connector_id)
- **api_connectors** → **api_connector_data**: One-to-Many (via connector_id)
- Foreign keys with CASCADE delete for data integrity

### Data Types

#### JSONB Usage
- **websocket_messages.data**: Complete message payload
- **websocket_batches.messages**: Array of messages
- **websocket_batches.metrics**: Performance metrics
- **connector_status.performance_metrics**: Connector metrics
- **api_connector_data.data**: Processed API response
- **api_connector_data.raw_response**: Raw API response

**Benefits of JSONB**:
- Efficient storage and querying
- Index support for JSON queries
- Flexible schema for varying data structures

#### Timestamp Handling
- All timestamps use `TIMESTAMP WITH TIME ZONE`
- Default to `NOW()` for automatic timestamping
- Supports timezone-aware queries

### Index Strategy

#### Primary Indexes
- All tables have `id SERIAL PRIMARY KEY`
- Unique constraints on `connector_id`

#### Composite Indexes
- `(timestamp DESC, exchange)` for time-based queries
- `(instrument, timestamp DESC)` for instrument history
- `(exchange, instrument, timestamp DESC)` for filtered queries

#### Query Optimization
Indexes designed for common query patterns:
- Recent messages by exchange
- Instrument price history
- Connector data retrieval
- Time-range queries

## API Design

### RESTful Principles

#### Resource Naming
- `/api/connectors` - Collection resource
- `/api/connectors/{id}` - Individual resource
- `/api/connectors/{id}/start` - Action resource

#### HTTP Methods
- `GET`: Retrieve resources
- `POST`: Create resources or trigger actions
- `PUT`: Update resources
- `DELETE`: Remove resources

#### Response Format
```json
{
  "data": {...},
  "status": "success",
  "message": "Operation completed"
}
```

### WebSocket API

#### Connection Lifecycle
1. Client connects to `/api/realtime`
2. Server accepts connection
3. Server sends initial "connected" message
4. Server broadcasts data updates
5. Client disconnects or server closes connection

#### Message Types
- `connected`: Initial connection confirmation
- `data_update`: New data available
- `ping`: Keepalive message
- `error`: Error notification

### Error Handling

#### HTTP Status Codes
- `200`: Success
- `400`: Bad Request (validation error)
- `404`: Not Found
- `500`: Internal Server Error

#### Error Response Format
```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Connector Architecture

### Base Connector Interface

```python
class BaseConnector(ABC):
    @abstractmethod
    async def connect(self):
        """Establish connection"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close connection"""
        pass
    
    @abstractmethod
    async def start(self):
        """Start data collection"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop data collection"""
        pass
```

### REST Connector Implementation

#### Polling Mechanism
```python
async def _poll_loop(self):
    while self.running:
        try:
            response = await self._make_request()
            await self.message_processor.process(response)
            await asyncio.sleep(self.polling_interval / 1000)
        except Exception as e:
            await self._handle_error(e)
```

#### Request Handling
- Configurable HTTP method (GET, POST, etc.)
- Custom headers support
- Query parameters
- Request body for POST requests
- Response parsing and validation

### WebSocket Connector Implementation

#### Connection Management
```python
async def connect(self):
    self.ws = await websockets.connect(self.url)
    await self._send_subscription()
    asyncio.create_task(self._receive_loop())
```

#### Reconnection Logic
- Exponential backoff: 1s, 2s, 4s, 8s, max 30s
- Maximum retry attempts: Configurable
- Health monitoring: Ping/pong keepalive

#### Message Buffering
- Buffer messages for batch processing
- Automatic batch saving (every 5s or 50 messages)
- Prevents database overload

## Message Processing Pipeline

### Processing Stages

```
Raw Message
    ↓
[1] Normalization
    - Extract common fields
    - Standardize format
    ↓
[2] Field Extraction
    - Instrument identification
    - Price extraction
    - Metadata extraction
    ↓
[3] Validation
    - Data type validation
    - Required field check
    ↓
[4] Database Save
    - Insert into appropriate table
    - Generate source_id and session_id
    ↓
[5] WebSocket Broadcast
    - Broadcast to connected clients
    - Include database metadata
```

### Normalization Logic

#### Exchange-Specific Parsing

**OKX Format**:
```python
if 'arg' in data and 'data' in data:
    instrument = data['arg']['instId']
    price = data['data'][0]['px']
```

**Binance Format**:
```python
if 'stream' in data:
    instrument = data['stream'].split('@')[0]
    price = data['data']['p']
```

**Custom Format**:
```python
# Generic extraction with fallbacks
instrument = extract_instrument(data)
price = extract_price(data)
```

### Error Recovery

- **Database Errors**: Logged, message not lost
- **WebSocket Errors**: Retry with exponential backoff
- **Processing Errors**: Error logged, continue processing

## Security Implementation

### Encryption Service

#### AES-256 Encryption
```python
from cryptography.fernet import Fernet

class EncryptionService:
    def __init__(self, key: str):
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        return self.cipher.decrypt(encrypted.encode()).decode()
```

#### Encrypted Fields
- API keys
- API secrets
- Bearer tokens
- Custom headers
- Query parameters

### Authentication Handlers

#### HMAC Authentication
```python
import hmac
import hashlib

def generate_hmac_signature(message, secret):
    return hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
```

#### API Key Authentication
```python
headers = {
    'X-API-Key': api_key
}
```

#### Bearer Token Authentication
```python
headers = {
    'Authorization': f'Bearer {token}'
}
```

### Input Validation

#### Pydantic Models
```python
class ConnectorCreate(BaseModel):
    name: str
    api_url: HttpUrl
    http_method: str = "GET"
    auth_type: AuthType
    polling_interval: int = Field(ge=100, le=60000)
```

Validation ensures:
- Type safety
- Value constraints
- Required fields
- URL format validation

## Performance Optimization

### Database Optimization

#### Connection Pooling
- **Min Size**: 5 connections (always available)
- **Max Size**: 20 connections (scales with load)
- **Timeout**: 10 seconds

#### Query Optimization
- Use indexes for all WHERE clauses
- Limit result sets with LIMIT
- Use pagination for large datasets
- Batch inserts for high throughput

#### JSONB Queries
```sql
-- Efficient JSONB query
SELECT * FROM websocket_messages
WHERE data->>'instrument' = 'BTC-USDT'
AND timestamp > NOW() - INTERVAL '1 hour'
```

### Async/Await Patterns

#### Concurrent Operations
```python
# Process multiple messages concurrently
tasks = [process_message(msg) for msg in messages]
await asyncio.gather(*tasks)
```

#### Non-Blocking I/O
- All database operations are async
- WebSocket operations are async
- HTTP requests use aiohttp (async)

### Caching Strategy

#### Connection Status Caching
- Cache connector status in memory
- Update on status changes
- Reduce database queries

#### Configuration Caching
- Cache connector configurations
- Refresh on updates
- Reduce database load

## Error Handling

### Error Categories

#### Connection Errors
- Database connection failures
- WebSocket connection failures
- Network timeouts

**Handling**:
- Retry with exponential backoff
- Log error details
- Update status in database

#### Processing Errors
- Invalid data format
- Missing required fields
- Processing exceptions

**Handling**:
- Log error with context
- Continue processing other messages
- Return error response to client

#### Validation Errors
- Invalid input data
- Missing required fields
- Type mismatches

**Handling**:
- Return 400 Bad Request
- Include validation error details
- Log validation failures

### Error Logging

```python
import logging

logger = logging.getLogger(__name__)
logger.error(
    f"Error processing message: {error}",
    extra={
        "connector_id": connector_id,
        "message_id": message_id,
        "error_type": type(error).__name__
    }
)
```

## Testing Strategy

### Unit Tests

#### Database Tests
```python
async def test_database_connection():
    pool = await connect_to_postgres()
    result = await pool.fetchval('SELECT 1')
    assert result == 1
```

#### Connector Tests
```python
async def test_rest_connector():
    connector = RESTConnector(...)
    await connector.start()
    # Verify connector is running
    assert connector.status == 'running'
```

### Integration Tests

#### API Endpoint Tests
```python
async def test_create_connector(client):
    response = await client.post('/api/connectors', json={...})
    assert response.status_code == 200
    assert response.json()['connector_id'] is not None
```

#### End-to-End Tests
- Create connector
- Start connector
- Verify data collection
- Check database storage
- Verify WebSocket broadcast

### Test Utilities

#### Test Database
- Use separate test database
- Clean up after tests
- Isolated test environment

#### Mock Services
- Mock external APIs
- Mock WebSocket connections
- Mock database for unit tests

## Deployment Architecture

### Production Setup

#### Application Server
- **Uvicorn**: ASGI server
- **Gunicorn**: Process manager (optional)
- **Workers**: 4-8 workers for high concurrency

#### Database
- **PostgreSQL**: Production database
- **Connection Pooling**: 10-20 connections
- **Backup**: Automated daily backups
- **Replication**: Master-slave setup (optional)

#### Monitoring
- **Logging**: Structured logging
- **Metrics**: Performance metrics
- **Alerts**: Error and performance alerts

### Scaling Strategies

#### Horizontal Scaling
- Multiple application instances
- Load balancer (nginx, HAProxy)
- Shared database
- Session affinity for WebSocket

#### Vertical Scaling
- Increase server resources
- Optimize database queries
- Connection pool tuning
- Cache frequently accessed data

### Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Configuration

```bash
# Production environment variables
POSTGRES_HOST=postgres-db
POSTGRES_PORT=5432
POSTGRES_USER=etl_user
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=etl_tool
ENCRYPTION_KEY=32-character-encryption-key
```

---

**Last Updated**: 2024
**Version**: 1.0.0

