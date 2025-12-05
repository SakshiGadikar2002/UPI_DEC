# Complete Data Flow Explanation: API Extraction → Backend → Database → UI

This document explains the complete journey of data from external APIs through the backend system to the database and finally displayed in the UI.

---

## 📊 **Overview: Complete Data Flow**

```
External API
    ↓
[1] REST Connector (Polling) / WebSocket Connector (Real-time)
    ↓
[2] Message Processing & Normalization
    ↓
[3] Database Storage (PostgreSQL)
    ↓
[4] Real-time WebSocket Broadcast
    ↓
[5] Frontend UI Display
```

---

## 🔄 **Phase 1: API Data Extraction**

### **1.1 Connector Creation (Frontend → Backend)**

**Location:** `frontend/src/components/APISection.jsx`

When a user creates a connector:
1. User fills in API URL, headers, query params, authentication
2. Frontend sends `POST /api/connectors` request
3. Backend creates connector configuration and stores in `api_connectors` table

**Key Code:**
```javascript
// Frontend creates connector
const response = await fetch('/api/connectors', {
  method: 'POST',
  body: JSON.stringify({
    name: "My API Connector",
    api_url: "https://api.example.com/data",
    http_method: "GET",
    headers: {...},
    query_params: {...},
    auth_type: "API_KEY",
    polling_interval: 1000
  })
})
```

**Backend Endpoint:** `backend/main.py` - `POST /api/connectors`
- Generates unique `connector_id` (e.g., `conn_abc123def456`)
- Encrypts sensitive data (headers, query params, credentials)
- Stores configuration in PostgreSQL `api_connectors` table

---

### **1.2 Connector Start (Frontend → Backend)**

**Location:** `frontend/src/components/APISection.jsx` → `backend/main.py`

When user clicks "Start" or "Extract":
1. Frontend sends `POST /api/connectors/{connector_id}/start`
2. Backend creates connector instance using `ConnectorFactory`
3. Connector starts polling loop (for REST) or WebSocket connection

**Backend Flow:**
```python
# backend/main.py
@app.post("/api/connectors/{connector_id}/start")
async def start_connector(connector_id: str):
    # Get connector manager
    connector_manager = get_connector_manager(message_processor)
    
    # Start connector (creates instance and begins polling/streaming)
    await connector_manager.start_connector(connector_id)
```

**Connector Factory:** `backend/connectors/connector_factory.py`
- Detects protocol (REST vs WebSocket) from URL
- Creates appropriate connector: `RESTConnector` or `WebSocketConnector`

---

### **1.3 REST API Polling (Backend)**

**Location:** `backend/connectors/rest_connector.py`

For REST APIs, the connector runs a polling loop:

```python
# REST Connector Polling Loop
async def _run_loop(self):
    while self._running:
        # 1. Make HTTP request
        response = await self._make_request()
        
        # 2. Process response
        await self._on_message(response)
        
        # 3. Wait for next poll
        await asyncio.sleep(self.polling_interval)
```

**HTTP Request Details:**
```python
async def _make_request(self):
    # Build URL with query parameters
    url = self._build_url()
    
    # Prepare headers (including auth)
    headers = self._prepare_headers()
    
    # Make async HTTP request
    async with self.session.request(
        method=self.http_method,  # GET, POST, etc.
        url=url,
        headers=headers,
        timeout=30
    ) as response:
        # Parse response
        if 'application/json' in content_type:
            raw_data = await response.json()
            # Extract nested data (handles OKX, Binance, etc. formats)
            data = self._extract_nested_data(raw_data)
        
        return {
            "status": "success",
            "data": data,  # Extracted/normalized data
            "raw_response": raw_data,  # Original response
            "status_code": response.status,
            "response_time_ms": response_time
        }
```

**Key Features:**
- Supports GET, POST, PUT, DELETE methods
- Handles authentication (API Key, HMAC, Bearer Token, Basic Auth)
- Extracts nested data from common API formats (OKX, Binance, KuCoin)
- Measures response time

---

### **1.4 Data Processing (Connector → Message Processor)**

**Location:** `backend/connectors/rest_connector.py` → `backend/services/message_processor.py`

When connector receives API response:

```python
# REST Connector processes response
async def process_message(self, message):
    # Normalize data structure
    return {
        "exchange": self._detect_exchange(),  # "binance", "okx", etc.
        "data": data,  # Extracted data
        "timestamp": datetime.utcnow().isoformat(),
        "connector_id": self.connector_id,
        "message_type": "rest_response",
        "raw_response": raw_response,
        "status_code": status_code,
        "response_time_ms": response_time_ms
    }
```

**Message Processor Normalization:**
```python
# backend/services/message_processor.py
async def process(self, message):
    # 1. Normalize message format
    normalized = self._normalize(message)
    # Extracts: exchange, instrument, price, data, timestamp
    
    # 2. Save to database
    if self.db_callback:
        await self.db_callback(normalized)
    
    # 3. Broadcast to WebSocket clients
    if self.websocket_callback:
        await self.websocket_callback(normalized)
    
    return normalized
```

**Normalization Logic:**
- Extracts `instrument` (symbol/pair) from data
- Extracts `price` (recursively searches nested structures)
- Standardizes timestamp format
- Detects exchange from URL or data structure

---

## 💾 **Phase 2: Database Storage**

### **2.1 Database Schema**

**Location:** `backend/database.py`

The system uses PostgreSQL with these key tables:

#### **`api_connectors` Table**
Stores connector configurations:
```sql
CREATE TABLE api_connectors (
    id SERIAL PRIMARY KEY,
    connector_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255),
    api_url TEXT,
    http_method VARCHAR(10),
    headers_encrypted TEXT,  -- Encrypted headers
    query_params_encrypted TEXT,  -- Encrypted query params
    auth_type VARCHAR(50),
    credentials_encrypted TEXT,  -- Encrypted credentials
    status VARCHAR(20),  -- 'inactive', 'running', 'stopped'
    polling_interval INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

#### **`api_connector_data` Table**
Stores actual API response data:
```sql
CREATE TABLE api_connector_data (
    id SERIAL PRIMARY KEY,
    connector_id VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE,
    exchange VARCHAR(50),
    instrument VARCHAR(100),
    price DECIMAL(20, 8),
    data JSONB NOT NULL,  -- Main data payload
    message_type VARCHAR(50),
    raw_response JSONB,  -- Original API response
    status_code INTEGER,
    response_time_ms DECIMAL(10, 3),
    source_id VARCHAR(50),  -- Unique ID for this data point
    session_id VARCHAR(100),  -- Session identifier
    FOREIGN KEY (connector_id) REFERENCES api_connectors(connector_id)
)
```

#### **`connector_status` Table**
Tracks connector runtime status:
```sql
CREATE TABLE connector_status (
    id SERIAL PRIMARY KEY,
    connector_id VARCHAR(100),
    status VARCHAR(20),  -- 'running', 'stopped', 'error'
    last_message_timestamp TIMESTAMP,
    message_count BIGINT,
    error_log TEXT,
    updated_at TIMESTAMP
)
```

---

### **2.2 Saving Data to Database**

**Location:** `backend/main.py` - `save_to_database()` function

When message processor calls `db_callback`:

```python
async def save_to_database(message: dict):
    pool = get_pool()
    async with pool.acquire() as conn:
        # Extract fields from normalized message
        connector_id = message.get("connector_id")
        exchange = message.get("exchange", "custom")
        instrument = message.get("instrument")
        price = message.get("price")
        data = message.get("data", {})
        timestamp = message.get("timestamp")
        
        # Generate unique IDs
        source_id = hashlib.md5(...).hexdigest()[:16]
        session_id = message.get("session_id", str(uuid.uuid4()))
        
        # Insert into api_connector_data table
        inserted_id = await conn.fetchval("""
            INSERT INTO api_connector_data (
                connector_id, timestamp, exchange, instrument, price, 
                data, message_type, raw_response, status_code, 
                response_time_ms, source_id, session_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
        """, connector_id, timestamp, exchange, instrument, price,
            json.dumps(data), message_type, 
            json.dumps(raw_response), status_code, 
            response_time_ms, source_id, session_id)
        
        # Also insert into websocket_messages for backward compatibility
        await conn.execute("""
            INSERT INTO websocket_messages (...)
            VALUES (...)
        """)
```

**Key Points:**
- Data stored as JSONB (PostgreSQL's JSON binary format) for flexible schema
- Both `data` (processed) and `raw_response` (original) are stored
- Indexes on `connector_id`, `timestamp`, `exchange`, `instrument` for fast queries
- Foreign key relationship ensures data integrity

---

## 📡 **Phase 3: Real-time WebSocket Broadcast**

### **3.1 Backend WebSocket Server**

**Location:** `backend/main.py` - `/api/realtime` WebSocket endpoint

When data is saved, it's also broadcast to connected frontend clients:

```python
# Connection manager for WebSocket clients
connection_manager = ConnectionManager()

async def broadcast_to_websocket(message: dict):
    """Broadcast message to all connected WebSocket clients"""
    # Add database record ID to message
    saved_record = await save_to_database(message)
    
    # Format message for frontend
    ws_message = {
        "type": "data_update",
        "id": saved_record["id"],
        "source_id": saved_record["source_id"],
        "session_id": saved_record["session_id"],
        "connector_id": saved_record["connector_id"],
        "timestamp": saved_record["timestamp"],
        "exchange": saved_record["exchange"],
        "instrument": saved_record["instrument"],
        "price": saved_record["price"],
        "data": saved_record["data"]
    }
    
    # Broadcast to all connected clients
    await connection_manager.broadcast(ws_message)
```

**WebSocket Endpoint:**
```python
@app.websocket("/api/realtime")
async def websocket_endpoint(websocket: WebSocket):
    await connection_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except:
        connection_manager.disconnect(websocket)
```

---

### **3.2 Frontend WebSocket Client**

**Location:** `frontend/src/utils/realtimeWebSocket.js`

Frontend connects to WebSocket for real-time updates:

```javascript
// Frontend WebSocket connection
const ws = getRealtimeWebSocket()
ws.connect()

ws.on('connected', () => {
  console.log('✅ WebSocket connected')
})

ws.on('message', (data) => {
  // Handle real-time data update
  if (data.type === 'data_update') {
    // Update UI with new data
    updateDataDisplay(data)
  }
})
```

**Integration in APISection:**
```javascript
// frontend/src/components/APISection.jsx
const ws = getRealtimeWebSocket()

ws.on('message', (message) => {
  if (message.type === 'data_update' && 
      message.connector_id === connectorId) {
    // Add new data to existing data array
    setData(prev => ({
      ...prev,
      data: [message, ...(prev.data || [])].slice(0, 1000),  // Keep last 1000
      totalRows: (prev.totalRows || 0) + 1
    }))
  }
})
```

---

## 🖥️ **Phase 4: UI Display**

### **4.1 Fetching Historical Data**

**Location:** `frontend/src/components/APISection.jsx`

When connector starts, frontend fetches existing data from database:

```javascript
const fetchDataFromDatabase = async (connectorId) => {
  // GET /api/connectors/{connector_id}/data
  const response = await fetch(
    `/api/connectors/${connectorId}/data?limit=1000&sort_by=timestamp&sort_order=-1`
  )
  
  const result = await response.json()
  
  if (result.data && result.data.length > 0) {
    // Format data for table display
    const formattedData = result.data.map(row => ({
      id: row.id,
      timestamp: row.timestamp,
      session_id: row.session_id,
      source_id: row.source_id,
      exchange: row.exchange,
      instrument: row.instrument,
      price: row.price,
      data: row.data,  // Processed data
      raw_data: row.raw_response  // Original response
    }))
    
    // Update state
    setData({
      source: 'Real-Time API Stream',
      data: formattedData,
      totalRows: result.total,
      connector_id: connectorId,
      status: 'running'
    })
  }
}
```

**Backend Endpoint:** `backend/main.py` - `GET /api/connectors/{connector_id}/data`

```python
@app.get("/api/connectors/{connector_id}/data")
async def get_connector_data(connector_id: str, limit: int = 100, skip: int = 0):
    pool = get_pool()
    
    # Get total count
    total_count = await conn.fetchval(
        "SELECT COUNT(*) FROM api_connector_data WHERE connector_id = $1",
        connector_id
    )
    
    # Get paginated data
    rows = await conn.fetch("""
        SELECT * FROM api_connector_data
        WHERE connector_id = $1
        ORDER BY timestamp DESC
        LIMIT $2 OFFSET $3
    """, connector_id, limit, skip)
    
    # Format for frontend
    return {
        "data": [format_row_for_table(row) for row in rows],
        "count": len(rows),
        "total": total_count,
        "skip": skip,
        "limit": limit
    }
```

---

### **4.2 Data Display Component**

**Location:** `frontend/src/components/DataDisplay.jsx`

The `DataDisplay` component renders data in a table:

```javascript
function DataDisplay({ sectionData }) {
  const { data, source, connector_id, status } = sectionData
  
  // Process data for table display
  const tableData = useMemo(() => {
    if (!data) return []
    return Array.isArray(data) ? data : [data]
  }, [data])
  
  return (
    <div className="data-table-container">
      <table className="data-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Timestamp</th>
            <th>Session ID</th>
            <th>Source ID</th>
            <th>Exchange</th>
            <th>Instrument</th>
            <th>Price</th>
            <th>Processed Data</th>
            <th>Raw Data</th>
          </tr>
        </thead>
        <tbody>
          {tableData.map((row, index) => (
            <tr key={row.id || index}>
              <td>{index + 1}</td>
              <td>{row.timestamp}</td>
              <td>{row.session_id}</td>
              <td>{row.source_id}</td>
              <td>{row.exchange}</td>
              <td>{row.instrument}</td>
              <td>{row.price}</td>
              <td>
                <pre>{JSON.stringify(row.data, null, 2)}</pre>
              </td>
              <td>
                <pre>{JSON.stringify(row.raw_data, null, 2)}</pre>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

**Features:**
- Pagination (100 rows per page)
- Real-time updates (new rows appear at top)
- Expandable JSON data columns
- Shows both processed and raw data
- Displays metadata (timestamp, session_id, source_id)

---

## 🔄 **Complete Flow Example**

### **Example: Binance Price API**

1. **User Creates Connector:**
   - URL: `https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT`
   - Method: GET
   - Polling: 1000ms

2. **Backend Creates Connector:**
   - `connector_id`: `conn_abc123`
   - Stored in `api_connectors` table

3. **User Starts Connector:**
   - Backend creates `RESTConnector` instance
   - Starts polling loop

4. **Every 1 Second:**
   ```
   RESTConnector._make_request()
     ↓
   HTTP GET → https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT
     ↓
   Response: {"symbol":"BTCUSDT","price":"50000.50"}
     ↓
   RESTConnector.process_message()
     ↓
   MessageProcessor.process()
     ↓
   Normalized: {
     exchange: "binance",
     instrument: "BTC-USDT",
     price: 50000.50,
     data: {"symbol":"BTCUSDT","price":"50000.50"},
     connector_id: "conn_abc123",
     timestamp: "2024-01-01T12:00:00Z"
   }
     ↓
   save_to_database()
     ↓
   INSERT INTO api_connector_data (...)
     ↓
   broadcast_to_websocket()
     ↓
   WebSocket message sent to frontend
   ```

5. **Frontend Receives:**
   - WebSocket message arrives
   - `APISection` updates state
   - `DataDisplay` re-renders with new row

6. **User Views Data:**
   - Table shows all historical data
   - New rows appear in real-time
   - Can expand JSON columns to see full data

---

## 📋 **Key Files Reference**

### **Backend:**
- `backend/main.py` - API endpoints, WebSocket server, database callbacks
- `backend/connectors/rest_connector.py` - REST API polling logic
- `backend/connectors/base_connector.py` - Base connector interface
- `backend/services/connector_manager.py` - Manages connector lifecycle
- `backend/services/message_processor.py` - Normalizes and routes messages
- `backend/database.py` - Database schema and connection pool

### **Frontend:**
- `frontend/src/components/APISection.jsx` - Connector creation and management
- `frontend/src/components/DataDisplay.jsx` - Data table display
- `frontend/src/utils/realtimeWebSocket.js` - WebSocket client

---

## 🎯 **Summary**

**Data Flow:**
1. **Extraction:** REST connector polls external API every N milliseconds
2. **Processing:** Message processor normalizes data (extracts exchange, instrument, price)
3. **Storage:** Data saved to PostgreSQL `api_connector_data` table (JSONB format)
4. **Broadcast:** Real-time WebSocket message sent to frontend
5. **Display:** Frontend fetches historical data + receives real-time updates → displays in table

**Key Technologies:**
- **Backend:** FastAPI, asyncpg (PostgreSQL), aiohttp (HTTP client)
- **Database:** PostgreSQL with JSONB for flexible data storage
- **Frontend:** React, WebSocket API
- **Real-time:** WebSocket for live updates, polling for historical data

**Data Storage:**
- Connector configs: `api_connectors` table
- API responses: `api_connector_data` table (JSONB)
- Status tracking: `connector_status` table

**Real-time Updates:**
- Backend broadcasts via WebSocket (`/api/realtime`)
- Frontend subscribes and updates UI automatically
- Historical data fetched via REST API (`GET /api/connectors/{id}/data`)

