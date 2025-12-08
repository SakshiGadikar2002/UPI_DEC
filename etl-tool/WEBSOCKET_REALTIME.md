# WebSocket Real-Time API Documentation

Complete guide to real-time WebSocket connections for streaming cryptocurrency data.

## Table of Contents

1. [Overview](#overview)
2. [Connection](#connection)
3. [Message Format](#message-format)
4. [Endpoints](#endpoints)
5. [Examples](#examples)
6. [Error Handling](#error-handling)
7. [Performance](#performance)
8. [Best Practices](#best-practices)

## Overview

The WebSocket API provides real-time streaming of cryptocurrency price data from Binance and OKX exchanges.

### Features

✅ Real-time price updates  
✅ Order book data  
✅ Trading volume information  
✅ Multiple data sources (Binance, OKX)  
✅ Automatic reconnection  
✅ Message buffering  
✅ Error recovery  

## Connection

### WebSocket URL

```
ws://localhost:8000/ws
wss://yourdomain.com/ws  (production with SSL)
```

### JavaScript Client

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');

// Handle connection opened
ws.onopen = (event) => {
    console.log('WebSocket connected');
    ws.send(JSON.stringify({
        type: 'subscribe',
        channels: ['binance_prices', 'binance_orderbook']
    }));
};

// Handle incoming messages
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
    updateUI(data);
};

// Handle errors
ws.onerror = (event) => {
    console.error('WebSocket error:', event);
};

// Handle disconnection
ws.onclose = (event) => {
    console.log('WebSocket closed');
    // Attempt reconnection after 3 seconds
    setTimeout(() => reconnect(), 3000);
};
```

### Python Client

```python
import asyncio
import websockets
import json

async def websocket_client():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        # Subscribe to channels
        await websocket.send(json.dumps({
            "type": "subscribe",
            "channels": ["binance_prices"]
        }))
        
        # Receive messages
        async for message in websocket:
            data = json.loads(message)
            print(f"Received: {data}")

asyncio.run(websocket_client())
```

## Message Format

### Server-to-Client Message

```json
{
    "type": "price_update",
    "connector_id": "binance_prices",
    "exchange": "binance",
    "instrument": "BTC/USDT",
    "price": 42150.50,
    "timestamp": "2025-12-08T16:30:45.123Z",
    "data": {
        "symbol": "BTCUSDT",
        "price": "42150.50",
        "priceChangePercent": "2.45"
    }
}
```

### Client-to-Server Commands

**Subscribe to channels:**
```json
{
    "type": "subscribe",
    "channels": ["binance_prices", "binance_orderbook"]
}
```

**Unsubscribe:**
```json
{
    "type": "unsubscribe",
    "channels": ["binance_prices"]
}
```

**Heartbeat (keep-alive):**
```json
{
    "type": "ping"
}
```

**Response:**
```json
{
    "type": "pong"
}
```

## Endpoints

### Primary WebSocket Endpoint

```
WS /ws
```

**Purpose:** Real-time price and market data streaming

**Supported Channels:**

| Channel | Source | Data Type | Frequency |
|---------|--------|-----------|-----------|
| `binance_prices` | Binance | Current prices | 10s (scheduled) |
| `binance_orderbook` | Binance | Order book | 10s (scheduled) |
| `binance_24hr` | Binance | 24h ticker | 10s (scheduled) |
| `coingecko_global` | CoinGecko | Global market | 10s (scheduled) |
| `coingecko_top` | CoinGecko | Top 100 coins | 10s (scheduled) |
| `coingecko_trending` | CoinGecko | Trending coins | 10s (scheduled) |
| `bitcoinprice` | OKX | BTC/USDT realtime | <1s |
| `ethprice` | OKX | ETH/USDT realtime | <1s |

### Test Endpoint

```
POST /ws/test
```

**Request:**
```json
{
    "message": "Hello, WebSocket!"
}
```

**Response:**
```json
{
    "type": "test_response",
    "message": "Broadcast to all connected clients",
    "timestamp": "2025-12-08T16:30:45.123Z"
}
```

## Examples

### Example 1: Real-Time Price Tracking

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
    ws.send(JSON.stringify({
        type: 'subscribe',
        channels: ['binance_prices', 'bitcoinprice']
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    // Update UI with latest prices
    if (data.type === 'price_update') {
        updatePriceDisplay(data.instrument, data.price);
    }
};

function updatePriceDisplay(instrument, price) {
    const element = document.getElementById(`price-${instrument}`);
    if (element) {
        element.textContent = `$${price.toLocaleString()}`;
        element.style.color = Math.random() > 0.5 ? 'green' : 'red';
    }
}
```

### Example 2: Order Book Monitoring

```javascript
const orderBooks = {};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.connector_id === 'binance_orderbook') {
        const { asks, bids } = data.data;
        
        // Store order book data
        orderBooks[data.instrument] = {
            asks: asks.slice(0, 10),  // Top 10 asks
            bids: bids.slice(0, 10),  // Top 10 bids
            timestamp: data.timestamp
        };
        
        renderOrderBook(data.instrument);
    }
};

function renderOrderBook(instrument) {
    const book = orderBooks[instrument];
    console.table(book.asks);
    console.table(book.bids);
}
```

### Example 3: Live Chart Updates

```javascript
import Chart from 'chart.js/auto';

const ctx = document.getElementById('priceChart').getContext('2d');
const chart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'BTC Price',
            data: [],
            borderColor: 'rgb(75, 192, 192)',
            tension: 0.1
        }]
    }
});

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.instrument === 'BTC/USDT') {
        // Keep last 100 prices
        if (chart.data.labels.length > 100) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
        }
        
        chart.data.labels.push(
            new Date(data.timestamp).toLocaleTimeString()
        );
        chart.data.datasets[0].data.push(data.price);
        chart.update();
    }
};
```

### Example 4: Multi-Exchange Comparison

```javascript
const priceData = {};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'price_update') {
        const key = data.instrument;
        
        if (!priceData[key]) {
            priceData[key] = {};
        }
        
        priceData[key][data.exchange] = {
            price: data.price,
            timestamp: data.timestamp
        };
        
        displayComparison(key);
    }
};

function displayComparison(instrument) {
    const prices = priceData[instrument];
    const exchanges = Object.keys(prices);
    const highestPrice = Math.max(...exchanges.map(e => prices[e].price));
    const lowestPrice = Math.min(...exchanges.map(e => prices[e].price));
    const spread = ((highestPrice - lowestPrice) / lowestPrice * 100).toFixed(2);
    
    console.log(`${instrument} - Spread: ${spread}%`);
    console.table(prices);
}
```

## Error Handling

### Connection Errors

```javascript
ws.onerror = (event) => {
    console.error('WebSocket error:', event);
    
    // Log error details
    const errorCode = event.code;
    const errorReason = event.reason;
    
    sendErrorAlert(`Connection error: ${errorCode} - ${errorReason}`);
};
```

### Reconnection Logic

```javascript
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_INTERVAL = 3000;

function connect() {
    try {
        ws = new WebSocket('ws://localhost:8000/ws');
        
        ws.onopen = () => {
            console.log('Connected');
            reconnectAttempts = 0;
            resubscribeChannels();
        };
        
        ws.onclose = () => {
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                console.log(`Reconnecting... (attempt ${reconnectAttempts})`);
                setTimeout(connect, RECONNECT_INTERVAL);
            } else {
                console.error('Max reconnection attempts reached');
            }
        };
    } catch (error) {
        console.error('Connection failed:', error);
        setTimeout(connect, RECONNECT_INTERVAL);
    }
}

let subscribedChannels = [];

function subscribe(channels) {
    subscribedChannels = channels;
    ws.send(JSON.stringify({
        type: 'subscribe',
        channels: channels
    }));
}

function resubscribeChannels() {
    if (subscribedChannels.length > 0) {
        subscribe(subscribedChannels);
    }
}

// Initial connection
connect();
```

### Message Validation

```javascript
function validateMessage(data) {
    if (!data || typeof data !== 'object') {
        console.warn('Invalid message format');
        return false;
    }
    
    // Check required fields
    const requiredFields = ['type', 'timestamp'];
    for (const field of requiredFields) {
        if (!(field in data)) {
            console.warn(`Missing required field: ${field}`);
            return false;
        }
    }
    
    // Validate timestamp
    const timestamp = new Date(data.timestamp);
    if (isNaN(timestamp.getTime())) {
        console.warn('Invalid timestamp');
        return false;
    }
    
    // Check message age (reject if older than 10 minutes)
    const age = Date.now() - timestamp.getTime();
    if (age > 600000) {
        console.warn('Message too old');
        return false;
    }
    
    return true;
}

ws.onmessage = (event) => {
    try {
        const data = JSON.parse(event.data);
        if (validateMessage(data)) {
            processMessage(data);
        }
    } catch (error) {
        console.error('Message parsing error:', error);
    }
};
```

## Performance

### Throughput

**Messages per second:**
```
With 8 scheduled APIs @ 10s interval:
Messages/sec = 8 APIs / 10 seconds = 0.8 msgs/sec

With realtime WebSocket streams:
Messages/sec = 100+ msgs/sec (per subscription)
```

### Latency

- **Scheduled APIs**: 100-200ms (batch interval variance)
- **Realtime streams**: <50ms (OKX WebSocket)
- **Network latency**: 20-100ms (depends on geography)
- **Processing**: <10ms (browser-side)

### Memory Usage

Per client connection:
- Message buffer: ~1MB
- Subscription tracking: ~10KB
- Client state: ~50KB
- **Total per client: ~1.1MB**

Server-side:
- Per connection: ~100KB
- Broadcast queue: ~10MB (for 100 concurrent clients)

### Bandwidth Usage

Per client:
- Inbound: ~1KB/sec (with 0.8 msgs/sec @ ~1.2KB per message)
- Outbound: Depends on subscriptions
- **Typical: 5-10KB/sec total**

## Best Practices

### 1. Connection Management

```javascript
// Close connection properly
function disconnect() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close(1000, 'Normal closure');
    }
}

// Clean up on page unload
window.addEventListener('beforeunload', disconnect);
```

### 2. Memory Management

```javascript
// Limit stored message history
const MAX_HISTORY = 1000;
let messageHistory = [];

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    messageHistory.push(data);
    
    // Remove old messages
    if (messageHistory.length > MAX_HISTORY) {
        messageHistory = messageHistory.slice(-MAX_HISTORY);
    }
};
```

### 3. Performance Optimization

```javascript
// Debounce UI updates
let updatePending = false;

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (!updatePending) {
        updatePending = true;
        
        requestAnimationFrame(() => {
            updateUI(data);
            updatePending = false;
        });
    }
};
```

### 4. Error Resilience

```javascript
// Circuit breaker pattern
class WebSocketManager {
    constructor(url) {
        this.url = url;
        this.failureCount = 0;
        this.maxFailures = 10;
        this.backoffDelay = 1000;
    }
    
    async connect() {
        if (this.failureCount >= this.maxFailures) {
            console.error('Circuit breaker: Too many failures');
            return false;
        }
        
        try {
            this.ws = new WebSocket(this.url);
            this.failureCount = 0;
            return true;
        } catch (error) {
            this.failureCount++;
            this.backoffDelay *= 2;
            await this.delay(this.backoffDelay);
            return this.connect();
        }
    }
    
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}
```

---

**Last Updated**: December 8, 2025  
**Version**: 1.0.0
