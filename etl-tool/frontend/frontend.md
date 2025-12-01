# Frontend Technical Documentation

Complete technical documentation for the ETL Tool React frontend application.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Core Components](#core-components)
5. [State Management](#state-management)
6. [Data Flow](#data-flow)
7. [WebSocket Integration](#websocket-integration)
8. [API Integration](#api-integration)
9. [Real-Time Features](#real-time-features)
10. [Styling](#styling)
11. [Configuration](#configuration)
12. [Build and Deployment](#build-and-deployment)

## Architecture Overview

The frontend is built using **React 18** with modern hooks and functional components. The application follows a component-based architecture with clear separation of concerns.

### Key Design Principles

- **Component-Based**: Modular, reusable components
- **Hooks-Based**: Modern React hooks for state and side effects
- **Real-Time Updates**: WebSocket integration for live data
- **Responsive Design**: Mobile-friendly UI
- **Performance Optimized**: Efficient rendering and data handling

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    React Application                      │
│                      (App.jsx)                           │
└──────────────┬──────────────────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────────┐    ┌───────▼────────┐
│  Header    │    │    Sidebar     │
│ Component  │    │   Component    │
└────────────┘    └───────┬────────┘
                         │
    ┌────────────────────┴────────────────────┐
    │                                          │
┌───▼────────┐    ┌───────▼────────┐    ┌─────▼────────┐
│   File     │    │      API       │    │  WebSocket   │
│  Upload    │    │    Section     │    │   Section   │
│  Section   │    │                │    │              │
└───┬────────┘    └───────┬────────┘    └─────┬────────┘
    │                     │                    │
    └─────────────────────┴────────────────────┘
                         │
                 ┌───────▼────────┐
                 │  DataDisplay   │
                 │   Component    │
                 └───────┬────────┘
                         │
    ┌────────────────────┴────────────────────┐
    │                                          │
┌───▼────────┐    ┌───────▼────────┐    ┌─────▼────────┐
│  Backend   │    │   WebSocket    │    │  LocalStorage│
│    API     │    │   Connection   │    │              │
└────────────┘    └────────────────┘    └──────────────┘
```

## Technology Stack

### Core Framework
- **React 18.2.0**: UI library
- **React DOM 18.2.0**: DOM rendering
- **Vite 5.0.8**: Build tool and dev server

### Data Visualization
- **Recharts 3.5.0**: Charting library
  - LineChart, AreaChart, BarChart, PieChart
  - ResponsiveContainer for adaptive sizing
  - Real-time chart updates

### Real-Time Communication
- **socket.io-client 4.8.1**: WebSocket client library

### Build Tools
- **@vitejs/plugin-react 4.2.1**: Vite React plugin
- **TypeScript Types**: Type definitions for React

## Project Structure

```
frontend/
├── index.html              # HTML entry point
├── vite.config.js          # Vite configuration
├── package.json            # Dependencies and scripts
│
└── src/
    ├── main.jsx            # React entry point
    ├── App.jsx             # Main application component
    ├── App.css             # Global styles
    ├── index.css           # Base styles
    │
    ├── components/         # React components
    │   ├── Header.jsx      # Top navigation header
    │   ├── Sidebar.jsx     # Side navigation
    │   ├── FileUploadSection.jsx    # File upload UI
    │   ├── APISection.jsx           # API connector UI
    │   ├── WebSocketSection.jsx     # WebSocket UI
    │   ├── DataDisplay.jsx          # Data table display
    │   ├── RealtimeStream.jsx      # Real-time charts
    │   ├── ErrorBoundary.jsx       # Error handling
    │   ├── HistoryModal.jsx        # History viewer
    │   ├── Icons.jsx               # SVG icons
    │   │
    │   └── *.css           # Component-specific styles
    │
    └── utils/              # Utility functions
        ├── backendCheck.js          # Backend health check
        ├── downloadUtils.js        # File download helpers
        ├── duplicateRemover.js     # Duplicate removal
        ├── jsonParser.js           # JSON parsing
        ├── realtimeWebSocket.js    # WebSocket utilities
        └── websocketConfig.js      # Exchange configurations
```

## Core Components

### 1. App Component (`App.jsx`)

Main application component that orchestrates all sections.

#### State Management
```javascript
const [activeSection, setActiveSection] = useState('files')
const [sidebarOpen, setSidebarOpen] = useState(true)
const [sectionData, setSectionData] = useState({
  files: null,
  api: null,
  websocket: null
})
const [history, setHistory] = useState([])
```

#### Key Features
- **Section Management**: Switches between File Upload, API, and WebSocket sections
- **History Management**: Stores and retrieves history from localStorage
- **Data Flow**: Manages data flow between sections and DataDisplay
- **Error Handling**: Wrapped in ErrorBoundary for error recovery

### 2. Header Component (`Header.jsx`)

Top navigation bar with history and settings.

**Features**:
- Sidebar toggle
- History modal
- Clear history functionality

### 3. Sidebar Component (`Sidebar.jsx`)

Left navigation sidebar.

**Sections**:
- File Upload
- API Section
- WebSocket Section

### 4. FileUploadSection Component

Handles file uploads (CSV, JSON).

**Features**:
- Drag-and-drop file upload
- File parsing and validation
- Data preview
- Duplicate removal
- Export functionality

### 5. APISection Component (`APISection.jsx`)

Manages API connector creation and real-time data streaming.

#### Key Features
- **Connector Creation**: Create API connectors via backend
- **Real-Time Streaming**: Connect to backend WebSocket for live updates
- **Data Display**: Show data in table format
- **Status Tracking**: Monitor connector status
- **Authentication**: Support for multiple auth methods

#### State Management
```javascript
const [apiUrl, setApiUrl] = useState('...')
const [httpMethod, setHttpMethod] = useState('GET')
const [connectorId, setConnectorId] = useState(null)
const [connectorStatus, setConnectorStatus] = useState('inactive')
const [wsConnected, setWsConnected] = useState(false)
```

### 6. WebSocketSection Component (`WebSocketSection.jsx`)

Manages WebSocket connections to exchanges.

#### Supported Exchanges
- **OKX**: OKX WebSocket streams
- **Binance**: Binance WebSocket streams
- **Custom**: Custom WebSocket endpoints

#### Features
- Exchange selection (OKX, Binance, Custom)
- Channel/instrument selection
- Real-time message display
- Connection status monitoring
- Performance metrics
- Multiple view modes (Stream, Dashboard, List, Compare)

#### View Modes
1. **Live Stream**: Real-time message feed
2. **Dashboard**: Charts and metrics
3. **List**: Instrument list with prices
4. **Compare**: Compare multiple instruments

### 7. RealtimeStream Component (`RealtimeStream.jsx`)

Advanced real-time data visualization component.

#### Features
- **Dashboard View**: Market overview with charts
- **List View**: Real-time instrument list
- **Compare View**: Multi-instrument comparison charts
- **Real-Time Updates**: Live data updates via WebSocket
- **Performance Metrics**: Latency, throughput tracking

#### Tracked Assets
20 major cryptocurrencies:
- BTC, ETH, BNB, SOL, XRP, ADA, DOGE, MATIC, DOT, AVAX
- SHIB, TRX, LINK, UNI, ATOM, LTC, ETC, XLM, ALGO, NEAR

### 8. DataDisplay Component (`DataDisplay.jsx`)

Displays data in tabular format.

**Features**:
- Sortable columns
- Search/filter functionality
- Pagination
- Export to CSV/JSON
- Responsive design

## State Management

### Local State (useState)

Each component manages its own local state:
- Form inputs
- UI state (modals, toggles)
- Component-specific data

### Global State (App.jsx)

App component manages:
- Active section
- Section data
- History
- Sidebar state

### Persistent State (localStorage)

- **History**: Stored in `etl-history` key
- **Settings**: User preferences (if implemented)

### Real-Time State (WebSocket)

- Live data updates
- Connection status
- Performance metrics

## Data Flow

### File Upload Flow

```
User Uploads File
    ↓
FileUploadSection parses file
    ↓
Data validated and processed
    ↓
setData() called with processed data
    ↓
App.jsx updates sectionData
    ↓
DataDisplay component renders table
```

### API Connector Flow

```
User Creates Connector
    ↓
POST /api/connectors
    ↓
Backend creates connector
    ↓
User Starts Connector
    ↓
POST /api/connectors/{id}/start
    ↓
Backend starts polling
    ↓
WebSocket connection established
    ↓
Real-time data received
    ↓
DataDisplay updates
```

### WebSocket Flow

```
User Connects to Exchange
    ↓
WebSocket connection established
    ↓
Messages received in real-time
    ↓
Messages saved to PostgreSQL (backend)
    ↓
WebSocket broadcast to frontend
    ↓
RealtimeStream component updates
    ↓
Charts and lists update
```

## WebSocket Integration

### Backend WebSocket (`/api/realtime`)

Frontend connects to backend WebSocket for real-time updates.

**Connection**:
```javascript
const ws = getRealtimeWebSocket()
ws.on('message', (message) => {
  // Handle real-time data
})
```

**Message Format**:
```json
{
  "type": "data_update",
  "id": 12345,
  "connector_id": "conn_abc",
  "timestamp": "2024-01-01T00:00:00Z",
  "exchange": "okx",
  "instrument": "BTC-USDT",
  "price": 50000.50,
  "data": {...}
}
```

### Exchange WebSocket

Direct connection to exchange WebSocket (OKX, Binance).

**OKX Connection**:
```javascript
const ws = new WebSocket('wss://ws.okx.com:8443/ws/v5/public')
ws.send(JSON.stringify({
  op: 'subscribe',
  args: [{channel: 'trades', instId: 'BTC-USDT'}]
}))
```

**Binance Connection**:
```javascript
const ws = new WebSocket('wss://stream.binance.com:9443/ws/btcusdt@trade')
```

## API Integration

### Backend API Base URL

```javascript
const API_BASE_URL = 'http://localhost:8000'
```

### Key API Endpoints Used

#### Connector Management
```javascript
// Create connector
POST /api/connectors

// Get connectors
GET /api/connectors

// Start connector
POST /api/connectors/{id}/start

// Get connector data
GET /api/connectors/{id}/data
```

#### WebSocket Data
```javascript
// Get WebSocket data
GET /api/websocket/data

// Get data count
GET /api/websocket/data/count
```

#### Database Status
```javascript
// Check PostgreSQL status
GET /api/postgres/status
```

### Error Handling

```javascript
try {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  const data = await response.json()
  return data
} catch (error) {
  console.error('API Error:', error)
  setError(error.message)
}
```

## Real-Time Features

### Real-Time Updates

1. **WebSocket Connection**: Persistent connection to backend
2. **Message Broadcasting**: Backend broadcasts new data
3. **State Updates**: React state updates trigger re-renders
4. **Chart Updates**: Recharts updates charts smoothly

### Performance Optimization

- **Debouncing**: Debounce rapid updates
- **Memoization**: useMemo for expensive calculations
- **Virtual Scrolling**: For large lists (if implemented)
- **Data Limiting**: Limit displayed data to prevent memory issues

### Real-Time Metrics

- **Message Rate**: Messages per second
- **Latency**: Processing latency
- **Throughput**: Data throughput over time
- **Uptime**: Connection uptime

## Styling

### CSS Architecture

- **Global Styles**: `App.css`, `index.css`
- **Component Styles**: Component-specific CSS files
- **Utility Classes**: Reusable utility classes

### Design System

- **Colors**: Consistent color palette
- **Typography**: Standard font sizes and weights
- **Spacing**: Consistent margins and padding
- **Components**: Reusable UI components

### Responsive Design

- **Mobile-First**: Mobile-friendly design
- **Breakpoints**: Responsive breakpoints
- **Flexible Layouts**: Flexbox and Grid layouts

## Configuration

### WebSocket Configuration (`utils/websocketConfig.js`)

#### OKX Configuration
```javascript
export const OKX_CONFIG = {
  WS_URL: 'wss://ws.okx.com:8443/ws/v5/public',
  INSTRUMENTS: {
    BTC_USDT: 'BTC-USDT',
    ETH_USDT: 'ETH-USDT',
    // ... 20 instruments
  }
}
```

#### Binance Configuration
```javascript
export const BINANCE_CONFIG = {
  WS_URL: 'wss://stream.binance.com:9443/ws/',
  SYMBOLS: {
    BTC_USDT: 'btcusdt',
    ETH_USDT: 'ethusdt',
    // ... 20 symbols
  }
}
```

### Environment Variables

Create `.env` file for configuration:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

## Build and Deployment

### Development

```bash
npm install
npm run dev
```

Starts development server at http://localhost:5173

### Production Build

```bash
npm run build
```

Creates optimized production build in `dist/` folder.

### Preview Production Build

```bash
npm run preview
```

### Deployment

#### Static Hosting

Build output can be deployed to:
- **Netlify**: Drag and drop `dist/` folder
- **Vercel**: Connect repository
- **GitHub Pages**: Deploy `dist/` folder
- **AWS S3**: Upload `dist/` folder

#### Docker (Example)

```dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=0 /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## Component Details

### FileUploadSection

**Props**:
- `data`: Current file data
- `setData`: Function to update data

**Features**:
- File drag-and-drop
- CSV/JSON parsing
- Data validation
- Duplicate removal
- Export functionality

### APISection

**Props**:
- `data`: Current API data
- `setData`: Function to update data

**Features**:
- API URL input
- HTTP method selection
- Authentication configuration
- Headers and query parameters
- Real-time data streaming
- Connector status monitoring

### WebSocketSection

**Props**:
- `data`: Current WebSocket data
- `setData`: Function to update data

**Features**:
- Exchange selection
- Instrument selection
- Real-time message stream
- Performance metrics
- Multiple view modes
- Connection management

### RealtimeStream

**Props**:
- `websocketData`: WebSocket data object
- `messages`: Array of messages
- `latencyData`: Latency metrics
- `throughputData`: Throughput metrics
- `defaultTab`: Default active tab
- `exchange`: Exchange name

**Features**:
- Dashboard view with market metrics
- List view with real-time prices
- Compare view with multi-instrument charts
- Real-time updates
- Performance tracking

## Utilities

### backendCheck.js

Checks if backend server is online.

```javascript
export async function checkBackendHealth() {
  try {
    const response = await fetch('http://localhost:8000/')
    return response.ok
  } catch {
    return false
  }
}
```

### duplicateRemover.js

Removes duplicate entries from data arrays.

### jsonParser.js

Parses and validates JSON data.

### downloadUtils.js

Handles file downloads (CSV, JSON).

### realtimeWebSocket.js

Manages WebSocket connection to backend.

## Best Practices

1. **Component Composition**: Break down into smaller components
2. **State Management**: Use appropriate state management (local vs global)
3. **Error Handling**: Always handle errors gracefully
4. **Performance**: Optimize re-renders with useMemo and useCallback
5. **Accessibility**: Use semantic HTML and ARIA attributes
6. **Code Splitting**: Lazy load components when possible
7. **Type Safety**: Use PropTypes or TypeScript for type checking

## Troubleshooting

### Common Issues

1. **Backend Not Connected**: Check backend is running on port 8000
2. **WebSocket Connection Failed**: Verify CORS settings
3. **Data Not Updating**: Check WebSocket connection status
4. **Build Errors**: Clear node_modules and reinstall
5. **CORS Errors**: Verify backend CORS configuration

### Debug Tips

- Use React DevTools for component inspection
- Check browser console for errors
- Monitor Network tab for API calls
- Use WebSocket tab for WebSocket messages

---

**Last Updated**: 2024
**Version**: 1.0.0

