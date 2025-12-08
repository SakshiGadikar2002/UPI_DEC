# Frontend Documentation

Complete guide to the React frontend application for the ETL Tool.

## Table of Contents

1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Components](#components)
5. [State Management](#state-management)
6. [API Integration](#api-integration)
7. [WebSocket Connection](#websocket-connection)
8. [Styling](#styling)
9. [Running the Application](#running-the-application)
10. [Build & Deployment](#build--deployment)

## Overview

The frontend is a modern React 18 application built with Vite for fast development and production builds. It provides:

- ✅ Real-time data streaming via WebSocket
- ✅ REST API data extraction and visualization
- ✅ File upload and processing (CSV, JSON)
- ✅ Interactive charts and metrics
- ✅ Connector management UI
- ✅ Message streaming and monitoring

## Technology Stack

### Frontend Framework
- **React 18.2+** - UI library
- **Vite 4+** - Build tool and dev server
- **CSS3** - Styling with modern features

### Utilities
- **JavaScript ES6+** - Modern JavaScript
- **Fetch API** - HTTP client
- **Native WebSocket** - Real-time communication
- **Local Storage** - Client-side persistence

### Development Tools
- **ESLint** - Code quality (if configured)
- **Prettier** - Code formatting (if configured)
- **npm** - Package manager

## Project Structure

```
frontend/
├── index.html                           # HTML entry point
├── package.json                         # Dependencies
├── vite.config.js                       # Vite configuration
│
├── src/
│   ├── main.jsx                         # React entry point
│   ├── App.jsx                          # Main application component
│   ├── App.css                          # Global styles
│   ├── index.css                        # Base styles
│   │
│   ├── components/                      # React components
│   │   ├── Header.jsx                   # Top navigation
│   │   ├── Sidebar.jsx                  # Side navigation
│   │   ├── APISection.jsx               # API testing section
│   │   ├── DataDisplay.jsx              # Data table view
│   │   ├── FileUploadSection.jsx        # File upload UI
│   │   ├── WebSocketSection.jsx         # WebSocket management
│   │   ├── RealtimeStream.jsx           # Live message stream
│   │   ├── HistoryModal.jsx             # Message history
│   │   ├── ResultsDisplay.jsx           # Results rendering
│   │   ├── VisualizationSection.jsx     # Charts & metrics
│   │   ├── ErrorBoundary.jsx            # Error handling
│   │   └── Icons.jsx                    # Icon utilities
│   │
│   ├── utils/                           # Utility functions
│   │   ├── backendCheck.js              # Backend connectivity
│   │   ├── cryptoMarketData.js          # Market data helpers
│   │   ├── downloadUtils.js             # Download utilities
│   │   ├── duplicateRemover.js          # Deduplication logic
│   │   ├── jsonParser.js                # JSON parsing
│   │   ├── realtimeWebSocket.js         # WebSocket manager
│   │   └── websocketConfig.js           # WebSocket settings
│   │
│   ├── styles/                          # Global styles
│   └── assets/                          # Images, icons (if any)
│
└── dist/                                # Build output (generated)
```

## Components

### Core Components

#### 1. App.jsx
Main application container that orchestrates all sections.

```jsx
function App() {
  const [backendStatus, setBackendStatus] = useState('checking');
  const [activeTab, setActiveTab] = useState('websocket');
  
  useEffect(() => {
    // Check backend connectivity
    checkBackendStatus();
  }, []);
  
  return (
    <div className="app">
      <Header status={backendStatus} />
      <div className="app-body">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
        <main className="main-content">
          {activeTab === 'websocket' && <WebSocketSection />}
          {activeTab === 'api' && <APISection />}
          {activeTab === 'upload' && <FileUploadSection />}
        </main>
      </div>
    </div>
  );
}
```

#### 2. Header.jsx
Top navigation bar with status indicators.

**Features:**
- Backend status (online/offline)
- Application title
- Navigation links

#### 3. Sidebar.jsx
Left navigation panel with section tabs.

**Tabs:**
- WebSocket Streaming
- Manual API Calls
- File Upload
- Data Visualization

#### 4. WebSocketSection.jsx
Real-time WebSocket data streaming interface.

**Features:**
- Connect/disconnect controls
- Channel subscription
- Live message stream
- Message filtering
- History modal
- Download capability

```jsx
function WebSocketSection() {
  const [wsConnected, setWsConnected] = useState(false);
  const [messages, setMessages] = useState([]);
  const [selectedChannels, setSelectedChannels] = useState([]);
  
  const handleConnect = async () => {
    const ws = new WebSocket('ws://localhost:8000/ws');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMessages(prev => [data, ...prev].slice(0, 1000));
    };
    setWsConnected(true);
  };
  
  return (
    <section className="websocket-section">
      <h2>Real-Time WebSocket Stream</h2>
      <button onClick={handleConnect}>
        {wsConnected ? 'Disconnect' : 'Connect'}
      </button>
      <div className="messages-container">
        {messages.map((msg, idx) => (
          <div key={idx} className="message-item">
            {JSON.stringify(msg, null, 2)}
          </div>
        ))}
      </div>
    </section>
  );
}
```

#### 5. APISection.jsx
Manual REST API testing interface.

**Features:**
- URL input
- Custom headers
- Method selection (GET, POST, etc.)
- Request body editor
- Response display
- Pretty JSON formatting

#### 6. FileUploadSection.jsx
File upload and processing UI.

**Supported Files:**
- CSV files
- JSON files

**Features:**
- Drag-and-drop upload
- File validation
- Progress indicator
- Result display

#### 7. DataDisplay.jsx
Table view for displaying results.

**Features:**
- Sortable columns
- Pagination
- Search/filter
- Export to CSV/JSON

#### 8. VisualizationSection.jsx
Charts and metrics display.

**Charts:**
- Line charts (price trends)
- Bar charts (volumes)
- Pie charts (distributions)

## State Management

### Local State

Use React hooks for component-level state:

```jsx
const [data, setData] = useState([]);
const [loading, setLoading] = useState(false);
const [error, setError] = useState(null);
```

### Local Storage

Persist data across sessions:

```javascript
// Save
localStorage.setItem('userPreferences', JSON.stringify({
  theme: 'dark',
  autoConnect: true
}));

// Load
const prefs = JSON.parse(localStorage.getItem('userPreferences'));
```

### WebSocket State

Manage WebSocket connection state:

```javascript
let ws = null;
let wsConnected = false;
let messageBuffer = [];

function connectWebSocket() {
  ws = new WebSocket('ws://localhost:8000/ws');
  
  ws.onopen = () => {
    wsConnected = true;
    flushMessageBuffer();
  };
  
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    handleMessage(message);
  };
}
```

## API Integration

### Backend Communication

#### Health Check

```javascript
async function checkBackendStatus() {
  try {
    const response = await fetch('http://localhost:8000/');
    if (response.ok) {
      return 'online';
    }
  } catch (error) {
    return 'offline';
  }
}
```

#### Data Retrieval

```javascript
async function fetchConnectorData(connectorId) {
  try {
    const response = await fetch(
      `http://localhost:8000/api/data/${connectorId}`
    );
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Fetch error:', error);
    return null;
  }
}
```

#### Data Extraction

```javascript
async function extractFromURL(url, headers = {}) {
  const response = await fetch('http://localhost:8000/api/data/extract', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers
    },
    body: JSON.stringify({ url })
  });
  
  return await response.json();
}
```

#### File Upload

```javascript
async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch('http://localhost:8000/api/data/upload', {
    method: 'POST',
    body: formData
  });
  
  return await response.json();
}
```

## WebSocket Connection

### Real-Time Data Streaming

```javascript
// In realtimeWebSocket.js

class WebSocketManager {
  constructor(url = 'ws://localhost:8000/ws') {
    this.url = url;
    this.ws = null;
    this.connected = false;
    this.listeners = new Map();
  }
  
  connect() {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);
        
        this.ws.onopen = () => {
          this.connected = true;
          console.log('WebSocket connected');
          resolve();
        };
        
        this.ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          this.emit('message', data);
        };
        
        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          reject(error);
        };
        
        this.ws.onclose = () => {
          this.connected = false;
          this.emit('disconnected');
        };
      } catch (error) {
        reject(error);
      }
    });
  }
  
  subscribe(channels) {
    if (this.connected) {
      this.ws.send(JSON.stringify({
        type: 'subscribe',
        channels: Array.isArray(channels) ? channels : [channels]
      }));
    }
  }
  
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }
  
  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(cb => cb(data));
    }
  }
  
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.connected = false;
    }
  }
}

export default new WebSocketManager();
```

### Usage in Components

```jsx
import wsManager from './utils/realtimeWebSocket';

function LiveComponent() {
  const [messages, setMessages] = useState([]);
  
  useEffect(() => {
    // Connect WebSocket
    wsManager.connect().then(() => {
      wsManager.subscribe(['binance_prices']);
    });
    
    // Listen for messages
    wsManager.on('message', (data) => {
      setMessages(prev => [data, ...prev].slice(0, 100));
    });
    
    // Cleanup
    return () => {
      wsManager.disconnect();
    };
  }, []);
  
  return (
    <div className="live-feed">
      {messages.map((msg, idx) => (
        <MessageItem key={idx} data={msg} />
      ))}
    </div>
  );
}
```

## Styling

### CSS Organization

```
styles/
├── App.css              # Global styles
├── index.css            # Reset and base styles
├── components/
│   ├── Header.css
│   ├── Sidebar.css
│   └── WebSocket.css
└── utils/
    ├── variables.css    # Colors, sizes, etc.
    └── mixins.css       # Reusable styles
```

### CSS Variables

```css
:root {
  /* Colors */
  --primary: #78176b;
  --secondary: #007bff;
  --success: #28a745;
  --danger: #dc3545;
  --warning: #ffc107;
  
  /* Spacing */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  
  /* Fonts */
  --font-primary: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto;
  --font-mono: 'Courier New', monospace;
}
```

### Responsive Design

```css
/* Mobile first */
.container {
  width: 100%;
  padding: var(--spacing-md);
}

/* Tablet and up */
@media (min-width: 768px) {
  .container {
    max-width: 750px;
    margin: 0 auto;
  }
}

/* Desktop and up */
@media (min-width: 1024px) {
  .container {
    max-width: 960px;
  }
}
```

## Running the Application

### Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server (Vite)
npm run dev

# Server runs on http://localhost:5173
```

### Building for Production

```bash
# Create production build
npm run build

# Output is in dist/ directory
```

### Preview Production Build

```bash
npm run preview

# Preview on http://localhost:4173
```

## Build & Deployment

### Build Process

```bash
npm run build
```

**Output:**
- `dist/index.html` - Main HTML file
- `dist/assets/` - JavaScript, CSS, and images

### Deploying to Production

#### Docker
```dockerfile
FROM node:18 AS build
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

#### Netlify
```bash
# Connect GitHub repo
# Set build command: npm run build
# Set publish directory: dist
```

#### Vercel
```bash
# Deploy with one command
vercel
```

#### Traditional Web Server
```bash
# Copy dist folder to web server
cp -r dist /var/www/etl-tool

# Configure nginx
server {
    listen 80;
    server_name yourdomain.com;
    root /var/www/etl-tool;
    index index.html;
}
```

## Performance Optimization

### Code Splitting

```javascript
// Lazy load components
const APISection = React.lazy(() => import('./components/APISection'));

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <APISection />
    </Suspense>
  );
}
```

### Asset Optimization

- Minify CSS/JS (automatic with Vite)
- Optimize images (convert to WebP)
- Enable gzip compression
- Use CDN for static assets

## Troubleshooting

### Backend Connection Issues

```javascript
// Check backend status
const response = await fetch('http://localhost:8000/');
if (!response.ok) {
  console.error('Backend unreachable');
}
```

### WebSocket Connection Failed

```javascript
// Check browser WebSocket support
if (!('WebSocket' in window)) {
  console.error('WebSocket not supported');
}

// Check CORS headers
// Ensure backend CORS allows frontend origin
```

### Data Not Loading

```javascript
// Add debugging
console.log('Fetching data...');
const data = await fetchConnectorData('binance_prices');
console.log('Received:', data);
```

---

**Last Updated**: December 8, 2025  
**Version**: 1.0.0
