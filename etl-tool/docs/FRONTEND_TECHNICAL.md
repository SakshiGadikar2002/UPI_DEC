# Frontend Technical Deep Dive

Comprehensive technical documentation covering all aspects of the frontend implementation.

## Table of Contents

1. [React Architecture](#react-architecture)
2. [Component Architecture](#component-architecture)
3. [State Management Patterns](#state-management-patterns)
4. [Real-Time Data Flow](#real-time-data-flow)
5. [WebSocket Integration](#websocket-integration)
6. [Data Visualization](#data-visualization)
7. [Performance Optimization](#performance-optimization)
8. [Build System](#build-system)
9. [Styling Architecture](#styling-architecture)
10. [Testing Strategy](#testing-strategy)

## React Architecture

### Component Hierarchy

```
App
├── ErrorBoundary
│   └── App Content
│       ├── Header
│       │   └── HistoryModal
│       ├── Sidebar
│       └── Main Content
│           ├── Section Components
│           │   ├── FileUploadSection
│           │   ├── APISection
│           │   └── WebSocketSection
│           │       └── RealtimeStream
│           │           ├── DashboardView
│           │           ├── ListView
│           │           └── CompareView
│           └── DataDisplay
```

### Hooks Usage

#### useState
- Component local state
- Form inputs
- UI state (modals, toggles)

#### useEffect
- Side effects (API calls, subscriptions)
- Lifecycle management
- Cleanup functions

#### useRef
- DOM references
- Mutable values that don't trigger re-renders
- Previous value storage

#### useMemo
- Expensive calculations
- Derived state
- Performance optimization

#### useCallback
- Memoized functions
- Prevent unnecessary re-renders
- Event handler optimization

### Component Patterns

#### Container/Presentational Pattern
- **Container**: Handles logic and state
- **Presentational**: Renders UI

#### Custom Hooks
- Reusable logic extraction
- State management abstraction
- Side effect encapsulation

## Component Architecture

### FileUploadSection

#### Responsibilities
- File upload handling
- File parsing (CSV, JSON)
- Data validation
- Duplicate removal
- Data export

#### State Management
```javascript
const [file, setFile] = useState(null)
const [loading, setLoading] = useState(false)
const [error, setError] = useState(null)
```

#### File Processing Flow
```
User selects file
    ↓
FileReader reads file
    ↓
Parse based on file type
    ↓
Validate data structure
    ↓
Remove duplicates
    ↓
Update parent component state
```

### APISection

#### Responsibilities
- API connector creation
- Real-time data streaming
- Connector status monitoring
- Data display management

#### WebSocket Integration
```javascript
useEffect(() => {
  if (connectorStatus === 'running') {
    const ws = getRealtimeWebSocket()
    ws.on('message', handleMessage)
    return () => ws.off('message', handleMessage)
  }
}, [connectorStatus])
```

#### Data Fetching
```javascript
const fetchDataFromDatabase = async (connectorId) => {
  const response = await fetch(
    `http://localhost:8000/api/connectors/${connectorId}/data?limit=1000`
  )
  const data = await response.json()
  setData(formatDataForDisplay(data.data))
}
```

### WebSocketSection

#### Exchange Support

**OKX Integration**:
```javascript
const OKX_CONFIG = {
  WS_URL: 'wss://ws.okx.com:8443/ws/v5/public',
  createSubscribeMessage: (channel, instId) => ({
    op: 'subscribe',
    args: [{ channel, instId }]
  })
}
```

**Binance Integration**:
```javascript
const BINANCE_CONFIG = {
  WS_URL: 'wss://stream.binance.com:9443/ws/',
  createStreamName: (symbol, streamType) => 
    `${symbol}@${streamType}`
}
```

#### Message Processing
```javascript
ws.onmessage = (event) => {
  const parsedData = JSON.parse(event.data)
  const normalized = normalizeMessage(parsedData)
  setMessages(prev => [normalized, ...prev])
  updateData(normalized)
}
```

### RealtimeStream Component

#### View Modes

**Dashboard View**:
- Market overview metrics
- Price charts
- Performance indicators
- Real-time updates

**List View**:
- Instrument list
- Real-time prices
- Price change indicators
- Mini charts

**Compare View**:
- Multi-instrument comparison
- Overlay charts
- Performance comparison
- Customizable selection

#### Data Processing
```javascript
const processHistoryData = useMemo(() => {
  return historyData.map(item => ({
    ...item,
    price: parseFloat(item.price),
    change1h: calculateChange(item, '1h'),
    change24h: calculateChange(item, '24h')
  }))
}, [historyData])
```

## State Management Patterns

### Local State (useState)

#### Component State
```javascript
const [count, setCount] = useState(0)
const [data, setData] = useState(null)
const [loading, setLoading] = useState(false)
```

#### Object State
```javascript
const [formData, setFormData] = useState({
  name: '',
  email: '',
  age: 0
})

// Update
setFormData(prev => ({ ...prev, name: 'New Name' }))
```

#### Array State
```javascript
const [items, setItems] = useState([])

// Add
setItems(prev => [...prev, newItem])

// Update
setItems(prev => prev.map(item => 
  item.id === id ? { ...item, ...updates } : item
))

// Remove
setItems(prev => prev.filter(item => item.id !== id))
```

### Lifted State

#### App-Level State
```javascript
// App.jsx
const [sectionData, setSectionData] = useState({
  files: null,
  api: null,
  websocket: null
})

// Passed to children
<APISection 
  data={sectionData.api}
  setData={(data) => updateSectionData('api', data)}
/>
```

### Context API (If Needed)

```javascript
const DataContext = createContext()

export const DataProvider = ({ children }) => {
  const [data, setData] = useState(null)
  return (
    <DataContext.Provider value={{ data, setData }}>
      {children}
    </DataContext.Provider>
  )
}
```

## Real-Time Data Flow

### WebSocket Connection Flow

```
Component Mounts
    ↓
useEffect triggers
    ↓
Create WebSocket connection
    ↓
Connection established
    ↓
Subscribe to data stream
    ↓
Messages received
    ↓
Update component state
    ↓
Trigger re-render
    ↓
Update UI (charts, tables)
```

### Data Update Cycle

```javascript
// 1. Receive message
ws.on('message', (message) => {
  // 2. Process message
  const processed = processMessage(message)
  
  // 3. Update state
  setData(prev => ({
    ...prev,
    data: [processed, ...prev.data].slice(0, 1000)
  }))
  
  // 4. Update metrics
  updateMetrics(processed)
})
```

### Performance Considerations

#### Debouncing Updates
```javascript
const debouncedUpdate = useMemo(
  () => debounce((data) => {
    setData(data)
  }, 100),
  []
)
```

#### Throttling Updates
```javascript
const throttledUpdate = useMemo(
  () => throttle((data) => {
    updateChart(data)
  }, 1000),
  []
)
```

## WebSocket Integration

### Backend WebSocket Connection

```javascript
import { getRealtimeWebSocket } from '../utils/realtimeWebSocket'

const ws = getRealtimeWebSocket()

ws.on('message', (message) => {
  if (message.type === 'data_update') {
    handleDataUpdate(message)
  }
})
```

### Exchange WebSocket Connection

```javascript
const ws = new WebSocket(wsUrl)

ws.onopen = () => {
  // Send subscription message
  ws.send(JSON.stringify(subscriptionMessage))
}

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  processMessage(data)
}

ws.onerror = (error) => {
  handleError(error)
}

ws.onclose = () => {
  handleReconnection()
}
```

### Connection Management

#### Auto-Reconnection
```javascript
const reconnect = () => {
  setTimeout(() => {
    if (reconnectAttempts < maxAttempts) {
      connectWebSocket()
      reconnectAttempts++
    }
  }, delay * Math.pow(2, reconnectAttempts))
}
```

#### Health Monitoring
```javascript
const healthCheck = setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ op: 'ping' }))
  }
}, 30000)
```

## Data Visualization

### Recharts Integration

#### Chart Types

**Line Chart**:
```javascript
<LineChart data={data}>
  <XAxis dataKey="time" />
  <YAxis />
  <Line dataKey="price" stroke="#8884d8" />
</LineChart>
```

**Area Chart**:
```javascript
<AreaChart data={data}>
  <Area dataKey="price" stroke="#8884d8" fill="#8884d8" />
</AreaChart>
```

**Bar Chart**:
```javascript
<BarChart data={data}>
  <Bar dataKey="volume" fill="#8884d8" />
</BarChart>
```

#### Real-Time Updates
```javascript
useEffect(() => {
  if (newData) {
    setChartData(prev => [...prev, newData].slice(-100))
  }
}, [newData])
```

### Performance Optimization

#### Memoization
```javascript
const chartData = useMemo(() => {
  return processDataForChart(rawData)
}, [rawData])
```

#### Virtualization
- Use react-window for large lists
- Render only visible items
- Reduce DOM nodes

## Performance Optimization

### React Optimization

#### Memo Components
```javascript
const ExpensiveComponent = React.memo(({ data }) => {
  return <div>{processData(data)}</div>
})
```

#### useMemo for Calculations
```javascript
const expensiveValue = useMemo(() => {
  return computeExpensiveValue(data)
}, [data])
```

#### useCallback for Functions
```javascript
const handleClick = useCallback(() => {
  doSomething(id)
}, [id])
```

### Rendering Optimization

#### Conditional Rendering
```javascript
{data && data.length > 0 && (
  <DataTable data={data} />
)}
```

#### Key Props
```javascript
{items.map(item => (
  <Item key={item.id} data={item} />
))}
```

### Data Management

#### Data Limiting
```javascript
const limitedData = useMemo(() => {
  return data.slice(0, 1000) // Keep only recent 1000 items
}, [data])
```

#### Cleanup
```javascript
useEffect(() => {
  const interval = setInterval(() => {
    // Update logic
  }, 1000)
  
  return () => clearInterval(interval)
}, [])
```

## Build System

### Vite Configuration

```javascript
// vite.config.js
export default {
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
}
```

### Build Process

#### Development
```bash
npm run dev
# Starts dev server with HMR
```

#### Production Build
```bash
npm run build
# Creates optimized production build
```

#### Build Output
- `dist/index.html`: Entry HTML
- `dist/assets/`: Optimized JS/CSS bundles
- Code splitting for optimal loading

### Code Splitting

#### Lazy Loading
```javascript
const RealtimeStream = React.lazy(() => 
  import('./components/RealtimeStream')
)

<Suspense fallback={<Loading />}>
  <RealtimeStream />
</Suspense>
```

## Styling Architecture

### CSS Organization

#### Global Styles
- `index.css`: Base styles, resets
- `App.css`: Application-wide styles

#### Component Styles
- Component-specific CSS files
- Scoped to component
- BEM naming convention (optional)

### CSS Patterns

#### Flexbox Layouts
```css
.container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
```

#### Grid Layouts
```css
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}
```

#### Responsive Design
```css
@media (max-width: 768px) {
  .container {
    flex-direction: column;
  }
}
```

### CSS Variables

```css
:root {
  --primary-color: #78176b;
  --secondary-color: #5d0f52;
  --text-color: #000000;
  --bg-color: #ffffff;
}
```

## Testing Strategy

### Unit Testing

#### Component Testing
```javascript
import { render, screen } from '@testing-library/react'
import APISection from './APISection'

test('renders API section', () => {
  render(<APISection />)
  expect(screen.getByText('API Section')).toBeInTheDocument()
})
```

#### Hook Testing
```javascript
import { renderHook, act } from '@testing-library/react'
import { useCounter } from './useCounter'

test('increments counter', () => {
  const { result } = renderHook(() => useCounter())
  act(() => {
    result.current.increment()
  })
  expect(result.current.count).toBe(1)
})
```

### Integration Testing

#### API Integration
```javascript
test('fetches connector data', async () => {
  const { getByText } = render(<APISection />)
  fireEvent.click(getByText('Start Connector'))
  await waitFor(() => {
    expect(getByText('Running')).toBeInTheDocument()
  })
})
```

### E2E Testing

#### User Flows
- Create connector
- Start data collection
- View data in table
- Export data

## Best Practices

### Code Organization
- Keep components small and focused
- Extract reusable logic to hooks
- Use meaningful variable names
- Comment complex logic

### Performance
- Optimize re-renders
- Use memoization appropriately
- Limit data size
- Clean up subscriptions

### Accessibility
- Use semantic HTML
- Add ARIA labels
- Keyboard navigation support
- Screen reader compatibility

### Error Handling
- Try-catch for async operations
- Error boundaries for component errors
- User-friendly error messages
- Error logging

---

**Last Updated**: 2024
**Version**: 1.0.0

