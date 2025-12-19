import { useState, useEffect, useRef } from 'react'
import './Section.css'
import { checkBackendHealth } from '../utils/backendCheck'
import { removeDuplicates } from '../utils/duplicateRemover'
import { getRealtimeWebSocket } from '../utils/realtimeWebSocket'
import PipelineViewer from './PipelineViewer'

function APISection({ data, setData }) {
  const apiBase = import.meta.env.VITE_API_BASE || ''
  // Start with an empty URL; user or Quick Connect will provide it.
  // This avoids hardcoding any specific provider (like Binance) in the UI state.
  const [apiUrl, setApiUrl] = useState('')
  const [httpMethod, setHttpMethod] = useState('GET')
  const [headers, setHeaders] = useState('{"Authorization": "Bearer token"}\n\nAuthorization: Bearer token')
  const [queryParams, setQueryParams] = useState('{"limit": 100, "page": 1}\n\nlimit=100&page=1')
  const [authentication, setAuthentication] = useState('None')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [bearerToken, setBearerToken] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  // Only one working ingestion mode: Streaming
  const [ingestionMode, setIngestionMode] = useState('Streaming')
  const [pollingInterval, setPollingInterval] = useState(1000)
  const [quickConnectExpanded, setQuickConnectExpanded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [backendOnline, setBackendOnline] = useState(false)
  const [checkingBackend, setCheckingBackend] = useState(true)
  const [connectorId, setConnectorId] = useState(null)
  const [connectorStatus, setConnectorStatus] = useState('inactive')
  const [wsConnected, setWsConnected] = useState(false)
  const [progress, setProgress] = useState({
    extract: { time: 0, status: 'idle' },
    transform: { time: 0, status: 'idle' },
    load: { time: 0, status: 'idle' }
  })
  const [activeApis, setActiveApis] = useState([])
  const [activeLoading, setActiveLoading] = useState(false)
  const [activeError, setActiveError] = useState('')
  const [selectedActiveApi, setSelectedActiveApi] = useState(null)
  const [showPipelineView, setShowPipelineView] = useState(false)
  const [pipelineViewExpanded, setPipelineViewExpanded] = useState(false)
  const [formExpanded, setFormExpanded] = useState(false)
  const [scheduledApisExpanded, setScheduledApisExpanded] = useState(false)
  const wsRef = useRef(null)
  const dataRef = useRef([])
  const lastUpdateTimeRef = useRef(0) // Track last update time for debouncing
  const lastStateDataRef = useRef(null) // Track last state data to prevent unnecessary updates
  const lastDataReceivedTimeRef = useRef(null) // Track when data was last received
  const streamHealthCheckRef = useRef(null) // Reference for stream health check interval
  const [authExamplesExpanded, setAuthExamplesExpanded] = useState(false)

  // Quick Connect configurations
  const quickConnectOptions = [
    {
      title: 'Binance - Order Book (BTC/USDT)',
      description: 'Get order book depth for BTC/USDT',
      url: 'https://api.binance.com/api/v3/depth?symbol=BTCUSDT',
      method: 'GET'
    },
    {
      title: 'Binance - Current Prices',
      description: 'Get current prices for all trading pairs',
      url: 'https://api.binance.com/api/v3/ticker/price',
      method: 'GET'
    },
    {
      title: 'Binance - 24hr Ticker Price',
      description: 'Get 24hr ticker price change statistics for all symbols',
      url: 'https://api.binance.com/api/v3/ticker/24hr',
      method: 'GET'
    },
    {
      title: 'CoinGecko - Global Market Data',
      description: 'Get global cryptocurrency market data',
      url: 'https://api.coingecko.com/api/v3/global',
      method: 'GET'
    },
    {
      title: 'CoinGecko - Top Cryptocurrencies',
      description: 'Get top 100 cryptocurrencies by market cap',
      url: 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false',
      method: 'GET'
    },
    {
      title: 'CoinGecko - Trending Coins',
      description: 'Get currently trending cryptocurrencies',
      url: 'https://api.coingecko.com/api/v3/search/trending',
      method: 'GET'
    },
    {
      title: 'CryptoCompare - Multi Price',
      description: 'Get current prices for multiple cryptocurrencies',
      url: 'https://min-api.cryptocompare.com/data/pricemulti?fsyms=BTC,ETH,BNB&tsyms=USD',
      method: 'GET'
    },
    {
      title: 'CryptoCompare - Top Coins',
      description: 'Get top cryptocurrencies by market cap',
      url: 'https://min-api.cryptocompare.com/data/top/mktcapfull?limit=10&tsym=USD',
      method: 'GET'
    }
  ]

  useEffect(() => {
    const verifyBackend = async () => {
      setCheckingBackend(true)
      const isOnline = await checkBackendHealth()
      setBackendOnline(isOnline)
      setCheckingBackend(false)
      if (!isOnline) {
        setError('Backend server is not running. Please start the backend server.')
      }
    }
    verifyBackend()
    // Check backend every 5 seconds
    const interval = setInterval(verifyBackend, 5000)
    return () => clearInterval(interval)
  }, [])
  
  // Reconnect WebSocket if connector is already running when component mounts
  // Reconnect WebSocket if connector is already running on mount
  // This is now handled by the main WebSocket useEffect that depends on connectorId/connectorStatus
  // Removed this useEffect to prevent conflicts with data updates
  
  // Auto-refresh data from api_connector_data table every 3 seconds if connector is running
  // This ensures the frontend always shows the latest data from the database
  useEffect(() => {
    if (connectorStatus === 'running' && connectorId) {
      console.log('🔄 Setting up auto-refresh for connector:', connectorId)
      
      // Initial fetch immediately
      console.log('🔄 Initial fetch from api_connector_data table...')
      fetchDataFromDatabase(connectorId)
      lastDataReceivedTimeRef.current = Date.now() // Initialize last data time
      
      // Then refresh every 30 minutes to get latest data from api_connector_data table
      // Increased interval significantly to reduce flickering
      const interval = setInterval(() => {
        console.log('🔄 Auto-refreshing from api_connector_data table...')
        fetchDataFromDatabase(connectorId)
      }, 1800000) // Refresh every 30 minutes (1800 seconds) to minimize flickering
      
      // Stream health check - detect if stream is stuck (no data for 2 minutes)
      streamHealthCheckRef.current = setInterval(() => {
        const now = Date.now()
        const timeSinceLastData = lastDataReceivedTimeRef.current 
          ? now - lastDataReceivedTimeRef.current 
          : 0
        
        // If no data received for 2 minutes (120000ms), consider stream stuck
        if (timeSinceLastData > 120000 && lastDataReceivedTimeRef.current !== null && connectorStatus === 'running') {
          console.error('⚠️ Stream appears to be stuck - no data received for 2 minutes')
          setError('⚠️ Real-time stream appears to be stuck. No data received for 2 minutes. The stream will be reset.')
          setConnectorStatus('error')
          
          // Clear health check to prevent multiple triggers
          if (streamHealthCheckRef.current) {
            clearInterval(streamHealthCheckRef.current)
            streamHealthCheckRef.current = null
          }
          
          // Reset to basic state after showing error
          setTimeout(async () => {
            await handleStopConnector()
            setError('Stream was reset due to inactivity. Please start a new stream.')
            lastDataReceivedTimeRef.current = null
          }, 3000) // Wait 3 seconds before resetting
        }
      }, 30000) // Check every 30 seconds
      
      return () => {
        console.log('🔄 Clearing auto-refresh interval')
        clearInterval(interval)
        if (streamHealthCheckRef.current) {
          clearInterval(streamHealthCheckRef.current)
          streamHealthCheckRef.current = null
        }
      }
    } else {
      // Clear health check when not running
      if (streamHealthCheckRef.current) {
        clearInterval(streamHealthCheckRef.current)
        streamHealthCheckRef.current = null
      }
      lastDataReceivedTimeRef.current = null
    }
  }, [connectorStatus, connectorId])

  const handleQuickConnect = (option) => {
    setApiUrl(option.url)
    setHttpMethod(option.method)
    setHeaders('')
    setQueryParams('')
    setAuthentication('None')
  }

  const parseHeaders = (headerString) => {
    if (!headerString || !headerString.trim()) return {}
    
    const lines = headerString.split('\n').filter(line => line.trim())
    const headers = {}
    
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      
      // Try JSON format first
      if (trimmed.startsWith('{')) {
        try {
          const parsed = JSON.parse(trimmed)
          Object.assign(headers, parsed)
          continue
        } catch (e) {
          // Not valid JSON, continue to key:value parsing
        }
      }
      
      // Try key:value format
      if (trimmed.includes(':')) {
        const colonIndex = trimmed.indexOf(':')
        const key = trimmed.substring(0, colonIndex).trim()
        const value = trimmed.substring(colonIndex + 1).trim()
        if (key) {
          headers[key] = value
        }
      }
    }
    
    return headers
  }

  const parseQueryParams = (queryString) => {
    if (!queryString || !queryString.trim()) return {}
    
    const lines = queryString.split('\n').filter(line => line.trim())
    const params = {}
    
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      
      // Try JSON format first
      if (trimmed.startsWith('{')) {
        try {
          const parsed = JSON.parse(trimmed)
          Object.assign(params, parsed)
          continue
        } catch (e) {
          // Not valid JSON, continue to key=value parsing
        }
      }
      
      // Try key=value format (URL encoded)
      if (trimmed.includes('=')) {
        const pairs = trimmed.split('&')
        for (const pair of pairs) {
          const equalIndex = pair.indexOf('=')
          if (equalIndex > 0) {
            const key = decodeURIComponent(pair.substring(0, equalIndex).trim())
            const value = decodeURIComponent(pair.substring(equalIndex + 1).trim())
            if (key) {
              params[key] = value
            }
          }
        }
      }
    }
    
    return params
  }

  const buildUrlWithParams = (baseUrl, params) => {
    if (!params || Object.keys(params).length === 0) return baseUrl
    
    try {
      const url = new URL(baseUrl)
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.set(key, value)
      })
      return url.toString()
    } catch (e) {
      // If URL parsing fails, try to append params manually
      const separator = baseUrl.includes('?') ? '&' : '?'
      const paramString = Object.entries(params)
        .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
        .join('&')
      return `${baseUrl}${separator}${paramString}`
    }
  }

  const fetchActiveApis = async () => {
    try {
      setActiveLoading(true)
      setActiveError('')
      const resp = await fetch(`${apiBase}/api/etl/active`)
      if (!resp.ok) {
        throw new Error(`Failed to load active APIs (${resp.status})`)
      }
      const data = await resp.json()
      setActiveApis(Array.isArray(data) ? data : [])
    } catch (err) {
      console.error('Failed to fetch active APIs', err)
      setActiveError(err.message || 'Unable to load active APIs')
    } finally {
      setActiveLoading(false)
    }
  }

  useEffect(() => {
    fetchActiveApis()
    const interval = setInterval(fetchActiveApis, 60000)
    return () => clearInterval(interval)
  }, [])

  const fetchDataFromDatabase = async (connectorIdToFetch = null) => {
    const idToUse = connectorIdToFetch || connectorId
    if (!idToUse) {
      console.log('❌ No connector ID to fetch data for')
      return
    }
    
    console.log(`🔄 Fetching data from api_connector_data table for connector: ${idToUse}`)
    
    try {
      const url = `/api/connectors/${idToUse}/data?limit=1000&sort_by=timestamp&sort_order=-1`
      console.log(`📡 API Call: GET ${url}`)
      
      const dataResponse = await fetch(url)
      
      console.log(`📡 Response status: ${dataResponse.status}`)
      
      if (dataResponse.ok) {
        const dataResult = await dataResponse.json()
        console.log(`✅✅✅ Received data from api_connector_data table:`)
        console.log(`   - Total records in DB: ${dataResult.total}`)
        console.log(`   - Records fetched: ${dataResult.count}`)
        console.log(`   - Data array length: ${dataResult.data ? dataResult.data.length : 0}`)
        
        if (dataResult.data && dataResult.data.length > 0) {
          console.log(`   - First record sample:`, dataResult.data[0])
        }
        
        if (dataResult.data && dataResult.data.length > 0) {
          // Update last data received time
          lastDataReceivedTimeRef.current = Date.now()
          
          // Backend already formats data for table display
          // Just ensure proper formatting for frontend
          const formattedData = dataResult.data.map(item => {
            const formatted = {
              id: item.id,
              source_id: item.source_id || item.id || '-',
              session_id: item.session_id || item.connector_id || connectorId,
              timestamp: item.timestamp ? new Date(item.timestamp).toLocaleString() : '-',
              connector_id: item.connector_id || connectorId,
              exchange: item.exchange || 'unknown',
              instrument: item.instrument || '-',
              price: item.price || '-',
              message_type: item.message_type || 'api_response',
              status_code: item.status_code || '-',
              response_time_ms: item.response_time_ms ? `${item.response_time_ms}ms` : '-'
            }
            
            // Format processed_data (the actual API response)
            if (item.processed_data) {
              if (Array.isArray(item.processed_data)) {
                formatted.processed_data = JSON.stringify(item.processed_data, null, 2)
                formatted.data_count = item.processed_data.length
              } else if (typeof item.processed_data === 'object') {
                formatted.processed_data = JSON.stringify(item.processed_data, null, 2)
              } else {
                formatted.processed_data = String(item.processed_data)
              }
            }
            
            // Format raw_data (raw response)
            if (item.raw_data) {
              if (Array.isArray(item.raw_data)) {
                formatted.raw_data = JSON.stringify(item.raw_data, null, 2)
              } else if (typeof item.raw_data === 'object') {
                formatted.raw_data = JSON.stringify(item.raw_data, null, 2)
              } else {
                formatted.raw_data = String(item.raw_data)
              }
            } else if (item.processed_data) {
              // Use processed_data as raw_data if raw_data not available
              formatted.raw_data = formatted.processed_data
            }
            
            return formatted
          })
          
          console.log(`✅ Formatted ${formattedData.length} records for display`)
          console.log('✅ Sample formatted data (first record):', formattedData[0])
          console.log('✅ All formatted data keys:', formattedData.length > 0 ? Object.keys(formattedData[0]) : 'no data')
          
          // STRICT comparison to prevent flickering - only update if data truly changed
          const prevDataLength = dataRef.current.length
          const newDataLength = formattedData.length
          
          // Compare first and last items by ID
          const prevFirstId = prevDataLength > 0 ? dataRef.current[0]?.id : null
          const prevLastId = prevDataLength > 0 ? dataRef.current[prevDataLength - 1]?.id : null
          const newFirstId = newDataLength > 0 ? formattedData[0]?.id : null
          const newLastId = newDataLength > 0 ? formattedData[newDataLength - 1]?.id : null
          
          // Also compare with last state that was actually set
          const lastStateData = lastStateDataRef.current
          const lastStateFirstId = lastStateData?.length > 0 ? lastStateData[0]?.id : null
          const lastStateLastId = lastStateData?.length > 0 ? lastStateData[lastStateData.length - 1]?.id : null
          
          // Data changed ONLY if: length changed OR first/last items are different from last state
          const dataChanged = prevDataLength !== newDataLength || 
                            newFirstId !== lastStateFirstId || 
                            newLastId !== lastStateLastId
          
          // Only update if data actually changed AND it's different from last state
          if ((dataChanged || prevDataLength === 0) && 
              (newFirstId !== lastStateFirstId || newLastId !== lastStateLastId || !lastStateData)) {
            dataRef.current = formattedData
            lastStateDataRef.current = formattedData // Store what we're setting
            
            // Update state with all required fields
            const newData = {
              source: 'Real-Time API Stream',
              url: apiUrl,
              data: formattedData,
              totalRows: formattedData.length,
              connector_id: idToUse,
              status: 'running',
              timestamp: new Date().toISOString()
            }
            
            console.log('✅✅✅ UPDATING STATE WITH DATA:', {
              dataLength: newData.data.length,
              connector_id: newData.connector_id,
              status: newData.status,
              dataChanged
            })
            
            setData(newData)
          } else {
            console.log('⏭️ Skipping state update - data unchanged')
            // Update refs but don't trigger state update
            dataRef.current = formattedData
          }
        } else {
          // No data yet, but still ensure connector_id and status are set so table shows
          console.log('No data found in database yet, but setting connector info so table shows')
          dataRef.current = []
          setData(prev => {
            const newData = {
              source: 'Real-Time API Stream',
              url: prev?.url || '',
              data: [],
              totalRows: 0,
              connector_id: idToUse, // Always set connector_id
              status: 'running', // Always set status
              timestamp: new Date().toISOString(),
              ...prev
            }
            console.log('✅ Setting empty data but with connector info:', {
              connector_id: newData.connector_id,
              status: newData.status,
              source: newData.source
            })
            return newData
          })
        }
      } else {
        const errorText = await dataResponse.text()
        console.error('Failed to fetch data:', errorText)
      }
    } catch (err) {
      console.error('Error fetching data from database:', err)
    }
  }

  const handleExtract = async () => {
    if (!apiUrl.trim()) {
      setError('Please enter an API URL')
      return
    }

    // Check backend before proceeding
    const isOnline = await checkBackendHealth()
    if (!isOnline) {
      setError('Backend server is not running. Please start the backend server.')
      setBackendOnline(false)
      return
    }
    setBackendOnline(true)

    // Clean up any existing connector/stream before starting new one
    if (connectorId && connectorStatus === 'running') {
      // Stop existing connector first
      await handleStopConnector()
      // Wait a bit for cleanup
      await new Promise(resolve => setTimeout(resolve, 500))
    }
    
    // Disconnect any existing WebSocket connection
    if (wsRef.current) {
      try {
        wsRef.current.disconnect()
      } catch (e) {
        console.log('WebSocket already disconnected or error disconnecting:', e)
      }
      wsRef.current = null
    }

    setLoading(true)
    setError(null)
    
    // Reset all state and refs for fresh start
    dataRef.current = []
    lastUpdateTimeRef.current = 0
    lastStateDataRef.current = null
    lastDataReceivedTimeRef.current = null
    setData(null)
    setWsConnected(false)

    try {
      // Validate authentication credentials before proceeding (check for empty strings and placeholder values)
      const isPlaceholder = (value) => {
        if (!value || value.trim() === '') return true
        const lower = value.toLowerCase().trim()
        return lower.includes('your-') || 
               lower.includes('enter ') || 
               lower.includes('example') ||
               lower === 'your-api-key-here' ||
               lower === 'your-binance-api-key' ||
               lower === 'your-binance-api-secret' ||
               lower === 'ghp_your_github_token_here'
      }

      if (authentication === 'API Key') {
        if (!apiKey || apiKey.trim() === '' || isPlaceholder(apiKey)) {
          setError('API Key is required for API Key authentication. Please enter a valid API key (not a placeholder).')
          setLoading(false)
          return
        }
      }
      if (authentication === 'HMAC') {
        if (!apiKey || apiKey.trim() === '' || isPlaceholder(apiKey) || 
            !apiSecret || apiSecret.trim() === '' || isPlaceholder(apiSecret)) {
          setError('API Key and Secret are required for HMAC authentication. Please enter valid credentials (not placeholders).')
          setLoading(false)
          return
        }
      }
      if (authentication === 'Bearer Token') {
        if (!bearerToken || bearerToken.trim() === '' || isPlaceholder(bearerToken)) {
          setError('Bearer Token is required for Bearer Token authentication. Please enter a valid bearer token (not a placeholder).')
          setLoading(false)
          return
        }
      }
      if (authentication === 'Basic Auth') {
        // Basic Auth example values are valid (user/passwd for httpbin)
        if (!username || username.trim() === '' || !password || password.trim() === '') {
          setError('Username and Password are required for Basic Auth. Please enter both credentials.')
          setLoading(false)
          return
        }
      }

      // Parse headers and query params
      const requestHeaders = parseHeaders(headers)
      const queryParamsObj = parseQueryParams(queryParams)
      
      // Prepare connector data
      const connectorData = {
        name: `Connector ${new Date().toLocaleString()}`,
        api_url: apiUrl,
        http_method: httpMethod,
        headers: Object.keys(requestHeaders).length > 0 ? requestHeaders : null,
        query_params: Object.keys(queryParamsObj).length > 0 ? queryParamsObj : null,
        auth_type: authentication,
        polling_interval: pollingInterval
      }
      
      // Add credentials based on auth type (validation already ensured they exist and are not placeholders)
      // Double-check here as a safety measure
      if (authentication === 'API Key') {
        const trimmedKey = apiKey.trim()
        if (!trimmedKey || trimmedKey === '') {
          setError('API Key cannot be empty. Please enter a valid API key.')
          setLoading(false)
          return
        }
        connectorData.api_key = trimmedKey
      } else if (authentication === 'HMAC') {
        const trimmedKey = apiKey.trim()
        const trimmedSecret = apiSecret.trim()
        if (!trimmedKey || !trimmedSecret) {
          setError('API Key and Secret cannot be empty. Please enter valid credentials.')
          setLoading(false)
          return
        }
        connectorData.api_key = trimmedKey
        connectorData.api_secret = trimmedSecret
      } else if (authentication === 'Bearer Token') {
        const trimmedToken = bearerToken.trim()
        if (!trimmedToken || trimmedToken === '') {
          setError('Bearer Token cannot be empty. Please enter a valid bearer token.')
          setLoading(false)
          return
        }
        connectorData.bearer_token = trimmedToken
      } else if (authentication === 'Basic Auth') {
        const trimmedUser = username.trim()
        const trimmedPass = password.trim()
        if (!trimmedUser || !trimmedPass) {
          setError('Username and Password cannot be empty. Please enter valid credentials.')
          setLoading(false)
          return
        }
        connectorData.username = trimmedUser
        connectorData.password = trimmedPass
      }
      
      // Log the connector data for debugging (without sensitive info)
      console.log('🔍 Creating connector with:', {
        ...connectorData,
        api_key: connectorData.api_key ? '***' : undefined,
        api_secret: connectorData.api_secret ? '***' : undefined,
        bearer_token: connectorData.bearer_token ? '***' : undefined,
        username: connectorData.username ? '***' : undefined,
        password: connectorData.password ? '***' : undefined
      })
      console.log('🔍 Auth type:', authentication)
      console.log('🔍 Has username:', !!connectorData.username, 'Has password:', !!connectorData.password)

      // Create connector with timeout
      console.log('📤 Sending connector creation request...')
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 30000) // 30 second timeout
      
      let createResponse
      try {
        createResponse = await fetch('/api/connectors', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(connectorData),
          signal: controller.signal
        })
        clearTimeout(timeoutId)
        console.log('📥 Received response:', createResponse.status, createResponse.statusText)
      } catch (error) {
        clearTimeout(timeoutId)
        if (error.name === 'AbortError') {
          setError('Request timeout: Backend took too long to respond. Please check backend logs.')
          setLoading(false)
          return
        }
        throw error
      }

      if (!createResponse.ok) {
        let errorMessage = 'Failed to create connector'
        try {
          const errorData = await createResponse.json()
          // Handle Pydantic validation errors
          if (errorData.detail) {
            if (Array.isArray(errorData.detail)) {
              // Pydantic validation errors come as an array
              errorMessage = errorData.detail.map(err => {
                if (typeof err === 'object' && err.loc && err.msg) {
                  return `${err.loc.join('.')}: ${err.msg}`
                }
                return String(err)
              }).join(', ')
            } else {
              errorMessage = errorData.detail
            }
          }
        } catch (e) {
          // If JSON parsing fails, use default message
          errorMessage = `HTTP ${createResponse.status}: ${createResponse.statusText}`
        }
        setError(errorMessage)
        setLoading(false)
        return
      }

      const connector = await createResponse.json()
      setConnectorId(connector.connector_id)

      // If real-time streaming, start the connector
      if (ingestionMode === 'Streaming') {
        const startResponse = await fetch(`/api/connectors/${connector.connector_id}/start`, {
          method: 'POST'
        })

        if (!startResponse.ok) {
          const errorData = await startResponse.json()
          throw new Error(errorData.detail || 'Failed to start connector')
        }

        setConnectorStatus('running')
        setError(null)
        
        // Initialize data array
        dataRef.current = []
        
        // Initialize with empty data first, but ensure all required fields are set
        try {
          const initialData = {
            source: 'Real-Time API Stream',
            url: apiUrl || '',
            data: [], // Always initialize as empty array
            totalRows: 0,
            connector_id: connector.connector_id,
            status: 'running',
            timestamp: new Date().toISOString()
          }
          console.log('✅ Setting initial data for connector:', initialData)
          setData(initialData)
        } catch (err) {
          console.error('Error setting initial data:', err)
          // Set minimal safe data structure
          setData({
            source: 'Real-Time API Stream',
            url: '',
            data: [],
            totalRows: 0,
            connector_id: connector.connector_id,
            status: 'running',
            timestamp: new Date().toISOString()
          })
        }
        
        // Force a re-render by ensuring the data panel is visible
        console.log('✅ Connector started, table should be visible now')
        
        // DON'T fetch immediately - let WebSocket setup first, then fetch
        // The WebSocket connected handler will trigger the fetch
        // This prevents race conditions
        
        // Connect to WebSocket for real-time updates
        const ws = getRealtimeWebSocket()
        wsRef.current = ws
        
        ws.on('message', (message) => {
          try {
            console.log('Received WebSocket message:', message)
            // The message from backend contains: exchange, instrument, price, data, message_type, timestamp, connector_id
            // Flatten the message for better table display
            if (message && message.type !== 'connected' && message.type !== 'ping') {
              // Create a flat object for table display (matching database format)
              const flatMessage = {
                id: message.id || `ws_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                source_id: message.source_id || message.id || Math.random().toString(36).substr(2, 9),
                session_id: message.session_id || message.connector_id || connectorId || '-',
                timestamp: message.timestamp ? new Date(message.timestamp).toLocaleString() : new Date().toLocaleString(),
                connector_id: message.connector_id || connectorId || '-',
                exchange: message.exchange || 'unknown',
                instrument: message.instrument || '-',
                price: message.price || '-',
                message_type: message.message_type || 'unknown',
                status_code: message.status_code || '-',
                response_time_ms: message.response_time_ms || '-'
              }
              
              // Format processed_data (the actual API response data)
              if (message.data) {
                if (Array.isArray(message.data)) {
                  flatMessage.processed_data = JSON.stringify(message.data, null, 2)
                  flatMessage.data_count = message.data.length
                } else if (typeof message.data === 'object' && message.data !== null) {
                  flatMessage.processed_data = JSON.stringify(message.data, null, 2)
                } else {
                  flatMessage.processed_data = String(message.data)
                }
              }
              
              // Format raw_data (use raw_response if available, otherwise use data)
              if (message.raw_response) {
                if (Array.isArray(message.raw_response)) {
                  flatMessage.raw_data = JSON.stringify(message.raw_response, null, 2)
                } else if (typeof message.raw_response === 'object') {
                  flatMessage.raw_data = JSON.stringify(message.raw_response, null, 2)
                } else {
                  flatMessage.raw_data = String(message.raw_response)
                }
              } else if (message.data) {
                flatMessage.raw_data = flatMessage.processed_data
              }
              
              // Update last data received time when WebSocket message arrives
              lastDataReceivedTimeRef.current = Date.now()
              
              // Check if message already exists (avoid duplicates)
              const existingIndex = dataRef.current.findIndex(item => 
                item.id === flatMessage.id || 
                (item.source_id === flatMessage.source_id && item.timestamp === flatMessage.timestamp)
              )
              
              if (existingIndex >= 0) {
                // Update existing message
                dataRef.current[existingIndex] = flatMessage
              } else {
                // Add new message at the beginning (most recent first)
                dataRef.current.unshift(flatMessage)
              }
              
              // Keep only last 1000 messages
              if (dataRef.current.length > 1000) {
                dataRef.current = dataRef.current.slice(0, 1000)
              }
              
              // STRICT debounce and comparison to prevent flickering
              // Only update state every 2 seconds max, and only if data actually changed
              const now = Date.now()
              const timeSinceLastUpdate = now - lastUpdateTimeRef.current
              const shouldUpdateByTime = timeSinceLastUpdate > 2000 // Update max once per 2 seconds
              
              if (shouldUpdateByTime) {
                // Check if data actually changed compared to last state
                const newDataArray = [...dataRef.current]
                const lastStateData = lastStateDataRef.current || []
                
                // Compare first items to see if data actually changed
                const newFirstId = newDataArray.length > 0 ? newDataArray[0]?.id : null
                const lastStateFirstId = lastStateData.length > 0 ? lastStateData[0]?.id : null
                const dataActuallyChanged = newFirstId !== lastStateFirstId || 
                                          newDataArray.length !== lastStateData.length
                
                if (dataActuallyChanged) {
                  lastUpdateTimeRef.current = now
                  lastStateDataRef.current = newDataArray // Store what we're setting
                  
                  // Update state to trigger re-render
                  setData(prev => {
                    try {
                      return {
                        source: prev?.source || 'Real-Time API Stream',
                        url: prev?.url || apiUrl,
                        data: newDataArray,
                        totalRows: newDataArray.length,
                        connector_id: prev?.connector_id || connectorId,
                        status: prev?.status || 'running',
                        timestamp: message.timestamp || new Date().toISOString()
                      }
                    } catch (err) {
                      console.error('Error updating state in WebSocket handler:', err)
                      return {
                        source: 'Real-Time API Stream',
                        url: apiUrl,
                        data: newDataArray,
                        totalRows: newDataArray.length,
                        connector_id: connectorId,
                        status: 'running',
                        timestamp: new Date().toISOString()
                      }
                    }
                  })
                  
                  console.log(`✅ Real-time update: Added/updated message. Total rows: ${newDataArray.length}`)
                } else {
                  console.log('⏭️ Skipping WebSocket state update - data unchanged')
                }
              } else {
                console.log('⏭️ Skipping WebSocket state update - too soon since last update')
              }
            }
          } catch (err) {
            console.error('Error processing WebSocket message:', err)
          }
        })
        
        ws.on('connected', () => {
          console.log('✅ WebSocket connected for real-time updates')
          setWsConnected(true)
          // Fetch existing data when WebSocket connects
          if (connector.connector_id) {
            fetchDataFromDatabase(connector.connector_id)
          }
        })
        
        ws.on('disconnected', () => {
          console.log('❌ WebSocket disconnected')
          setWsConnected(false)
        })
        
        ws.on('error', (error) => {
          console.error('WebSocket error:', error)
          setError(`WebSocket error: ${error.message || 'Connection failed'}`)
        })
        
        ws.on('error', (error) => {
          console.error('WebSocket error:', error)
        })
        
        ws.connect()
      } else {
        // For one-time fetch, do a single request
        const finalUrl = buildUrlWithParams(apiUrl, queryParamsObj)
        const response = await fetch(finalUrl, {
          method: httpMethod,
          headers: requestHeaders
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const contentType = response.headers.get('content-type') || ''
        let extractedData = []
        
        if (contentType.includes('application/json')) {
          const jsonData = await response.json()
          if (Array.isArray(jsonData)) {
            extractedData = jsonData
          } else if (jsonData.data && Array.isArray(jsonData.data)) {
            extractedData = jsonData.data
          } else {
            extractedData = [jsonData]
          }
        } else {
          extractedData = [{ raw: await response.text() }]
        }

        const { uniqueData } = removeDuplicates(extractedData)
        
        setData({
          source: 'API Link',
          url: finalUrl,
          data: uniqueData,
          totalRows: uniqueData.length,
          timestamp: new Date().toISOString()
        })
      }
    } catch (err) {
      setError(`Error: ${err.message}`)
      setConnectorStatus('error')
    } finally {
      setLoading(false)
    }
  }

  const handleStopConnector = async () => {
    if (!connectorId) return
    
    try {
      const response = await fetch(`/api/connectors/${connectorId}/stop`, {
        method: 'POST'
      })
      
      if (response.ok) {
        setConnectorStatus('stopped')
        setWsConnected(false)
        // Disconnect WebSocket
        if (wsRef.current) {
          try {
            wsRef.current.disconnect()
          } catch (e) {
            console.log('WebSocket already disconnected')
          }
          wsRef.current = null
        }
        // Clear health check
        if (streamHealthCheckRef.current) {
          clearInterval(streamHealthCheckRef.current)
          streamHealthCheckRef.current = null
        }
        // Reset all refs and state
        lastDataReceivedTimeRef.current = null
        dataRef.current = []
        lastUpdateTimeRef.current = 0
        lastStateDataRef.current = null
        // Clear data from UI
        setData(null)
        // Reset connector state
        setConnectorId(null)
        setConnectorStatus('inactive')
        setError(null)
      }
    } catch (err) {
      setError(`Error stopping connector: ${err.message}`)
    }
  }
  
  const handleStartOrStopStream = async () => {
    if (connectorStatus === 'running') {
      // Stop the stream
      await handleStopConnector()
    } else {
      // Start the stream
      await handleExtract()
    }
  }
  
  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.disconnect()
      }
    }
  }, [])

  return (
    <div className="section-container">
      <div className="section-header">
        <div className="section-header-top">
          <div>
            <h2>API Links Section</h2>
            <p>Extract data from REST API endpoints (non-realtime)</p>
          </div>
          <button 
            className="collapse-toggle"
            onClick={() => setQuickConnectExpanded(!quickConnectExpanded)}
            aria-label={quickConnectExpanded ? 'Collapse Quick Connect' : 'Expand Quick Connect'}
            title={quickConnectExpanded ? 'Collapse Quick Connect' : 'Expand Quick Connect'}
          >
            <span className={`collapse-icon ${quickConnectExpanded ? 'expanded' : ''}`}>▼</span>
          </button>
        </div>
      </div>

      <div className="section-content">
        <div className="active-api-panel">
          <div className="active-api-header">
            <div>
              <h3>Scheduled APIs (Job Scheduler)</h3>
            </div>
            <div className="active-api-actions" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button
                className="extract-button-small"
                onClick={fetchActiveApis}
                disabled={activeLoading}
              >
                {activeLoading ? 'Refreshing...' : 'Refresh'}
              </button>
              <button 
                className="collapse-toggle"
                onClick={() => setScheduledApisExpanded(!scheduledApisExpanded)}
                aria-label={scheduledApisExpanded ? 'Collapse Scheduled APIs' : 'Expand Scheduled APIs'}
                title={scheduledApisExpanded ? 'Collapse Scheduled APIs' : 'Expand Scheduled APIs'}
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px 8px' }}
              >
                <span className={`collapse-icon ${scheduledApisExpanded ? 'expanded' : ''}`}>▼</span>
              </button>
            </div>
          </div>
          {scheduledApisExpanded && (
            <>
              {activeError && <div className="error-message">{activeError}</div>}
              <div className="active-api-grid">
            {activeLoading && activeApis.length === 0 && (
              <div className="active-api-hint">Loading scheduled APIs…</div>
            )}
            {!activeLoading && activeApis.length === 0 && (
              <div className="active-api-hint">No active APIs detected yet.</div>
            )}
            {activeApis.map((api) => {
              const lastSeen = api.last_timestamp
                ? new Date(api.last_timestamp).toLocaleString()
                : 'No data yet'
              return (
                <div className="pipeline-card-enhanced" key={api.connector_id}>
                  <div className="pipeline-card-header">
                    <div className="pipeline-card-title-group">
                      {api.status === 'ACTIVE' && (
                        <span className="pipeline-status-indicator active"></span>
                      )}
                      <div className="pipeline-card-title-info">
                        <h4 className="pipeline-card-name">{api.name}</h4>
                        <p className="pipeline-card-url">{api.api_url}</p>
                      </div>
                    </div>
                    <button
                      className="pipeline-view-button"
                      onClick={() => {
                        setSelectedActiveApi(api.connector_id)
                        setShowPipelineView(true)
                        setPipelineViewExpanded(true)
                      }}
                    >
                      View Pipeline →
                    </button>
                  </div>
                  <div className="pipeline-card-stats">
                    <div className="pipeline-stat-item">
                      <span className="pipeline-stat-label">Status</span>
                      <span className={`pipeline-stat-value status-${api.status?.toLowerCase() || 'inactive'}`}>
                        {api.status || 'INACTIVE'}
                      </span>
                    </div>
                    <div className="pipeline-stat-item">
                      <span className="pipeline-stat-label">Records</span>
                      <span className="pipeline-stat-value">{api.total_records || 0}</span>
                    </div>
                    <div className="pipeline-stat-item">
                      <span className="pipeline-stat-label">Items</span>
                      <span className="pipeline-stat-value">{api.total_items || 0}</span>
                    </div>
                    <div className="pipeline-stat-item">
                      <span className="pipeline-stat-label">Last Data</span>
                      <span className="pipeline-stat-value time">{lastSeen}</span>
                    </div>
                  </div>
                </div>
              )
            })}
              </div>
            </>
          )}
        </div>

        {showPipelineView && selectedActiveApi && (
          <div className="collapsible-section">
            <div className="collapsible-header" onClick={() => setPipelineViewExpanded(!pipelineViewExpanded)}>
              <h3>View Pipeline</h3>
              <button 
                className="collapse-toggle"
                onClick={(e) => {
                  e.stopPropagation()
                  setPipelineViewExpanded(!pipelineViewExpanded)
                }}
                aria-label={pipelineViewExpanded ? 'Collapse Pipeline View' : 'Expand Pipeline View'}
              >
                <span className={`collapse-icon ${pipelineViewExpanded ? 'expanded' : ''}`}>▼</span>
              </button>
            </div>
            {pipelineViewExpanded && (
              <div className="collapsible-content">
                <div className="active-pipeline-wrapper">
                  <PipelineViewer visible apiId={selectedActiveApi} onClose={() => {
                    setShowPipelineView(false)
                    setPipelineViewExpanded(false)
                  }} />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Quick Connect Section - Collapsible */}
        {quickConnectExpanded && (
          <div className="quick-connect-section">
            <div className="quick-connect-header">
              <h3>
                <span className="rocket-icon">🚀</span>
                Quick Connect - Non-Realtime Crypto Data
              </h3>
              <p>Click any button below to instantly connect to real-time cryptocurrency data:</p>
            </div>
            <div className="quick-connect-grid">
              {quickConnectOptions.map((option, index) => (
                <button
                  key={index}
                  className="quick-connect-btn"
                  onClick={() => handleQuickConnect(option)}
                  disabled={!backendOnline}
                >
                  <div className="quick-connect-title">{option.title}</div>
                  <div className="quick-connect-desc">{option.description}</div>
                </button>
              ))}
            </div>
            {/* OR Divider */}
            <div className="or-divider">
              <div className="or-line"></div>
              <span className="or-text">OR</span>
              <div className="or-line"></div>
            </div>
          </div>
        )}

        {/* Manual API Configuration */}
        <div className="collapsible-section">
          <div className="collapsible-header" onClick={() => setFormExpanded(!formExpanded)}>
            <h3>API Configuration Form</h3>
            <button 
              className="collapse-toggle"
              onClick={(e) => {
                e.stopPropagation()
                setFormExpanded(!formExpanded)
              }}
              aria-label={formExpanded ? 'Collapse Form' : 'Expand Form'}
            >
              <span className={`collapse-icon ${formExpanded ? 'expanded' : ''}`}>▼</span>
            </button>
          </div>
          {formExpanded && (
            <div className="collapsible-content">
              <div className="manual-api-config">
          <div className="api-config-row">
            <div className="input-group">
              <label>API URL</label>
              <input
                type="text"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="https://api.example.com/data"
                className="url-input"
                disabled={!backendOnline}
              />
            </div>
            <div className="input-group">
              <label>HTTP Method</label>
              <select
                value={httpMethod}
                onChange={(e) => setHttpMethod(e.target.value)}
                className="url-input"
                disabled={!backendOnline}
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="PATCH">PATCH</option>
                <option value="DELETE">DELETE</option>
              </select>
            </div>
          </div>

          <div className="api-config-row">
            <div className="input-group">
              <label>Headers (JSON or key:value format)</label>
              <textarea
                value={headers}
                onChange={(e) => setHeaders(e.target.value)}
                placeholder='{"Authorization": "Bearer token"}\n\nAuthorization: Bearer token'
                className="headers-textarea"
                rows={4}
                disabled={!backendOnline}
              />
            </div>
            <div className="input-group">
              <label>Query Parameters (JSON or key=value format)</label>
              <textarea
                value={queryParams}
                onChange={(e) => setQueryParams(e.target.value)}
                placeholder='{"limit": 100, "page": 1}\n\nlimit=100&page=1'
                className="headers-textarea"
                rows={4}
                disabled={!backendOnline}
              />
            </div>
          </div>

          <div className="api-config-row">
            <div className="input-group">
              <label>Authentication</label>
              <select
                value={authentication}
                onChange={(e) => setAuthentication(e.target.value)}
                className="url-input"
                disabled={!backendOnline}
              >
                <option value="None">None - No authentication required</option>
                <option value="API Key">API Key - Simple API key in headers</option>
                <option value="Bearer Token">Bearer Token - OAuth 2.0 Bearer token</option>
                <option value="Basic Auth">Basic Auth - HTTP Basic Authentication</option>
              </select>
            </div>
            <div className="input-group">
              <label>Ingestion Mode</label>
              <select
                value={ingestionMode}
                className="url-input"
                disabled
              >
                <option value="Streaming">Streaming</option>
              </select>
            </div>
          </div>

          {ingestionMode === 'Streaming' && (
            <div className="api-config-row">
              <div className="input-group">
                <label>Polling Interval (ms) - REST only</label>
                <input
                  type="number"
                  value={pollingInterval}
                  onChange={(e) => setPollingInterval(parseInt(e.target.value) || 1000)}
                  min="100"
                  max="60000"
                  step="100"
                  className="url-input"
                  disabled={!backendOnline}
                />
              </div>
              <div className="input-group"></div>
            </div>
          )}

          {authentication === 'API Key' && (
            <div className="input-group">
              <label>API Key <span style={{ color: '#f44336' }}>*</span></label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your real API key (required)"
                className="url-input"
                disabled={!backendOnline}
              />
              <small style={{ color: '#666', fontSize: '0.85rem', marginTop: '5px', display: 'block' }}>
                💡 <strong>Required:</strong> You must enter a valid API key. Placeholder values like "your-api-key-here" are not accepted.<br/>
                <strong>How it works:</strong> API Key will be added to headers as <code>X-API-Key</code> header.<br/>
                <strong>Test URL:</strong> <code>https://httpbin.org/headers</code> - This endpoint shows all request headers, so you can verify your API key is being sent correctly.<br/>
                <strong>💡 Tip:</strong> Use any API key value (e.g., "test-key-123") with httpbin.org/headers to test - it will show your API key in the response!
              </small>
            </div>
          )}

          {authentication === 'HMAC' && (
            <>
              <div className="input-group">
                <label>API Key <span style={{ color: '#f44336' }}>*</span></label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter your real API key (required)"
                  className="url-input"
                  disabled={!backendOnline}
                />
              </div>
              <div className="input-group">
                <label>API Secret <span style={{ color: '#f44336' }}>*</span></label>
                <input
                  type="password"
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  placeholder="Enter your real API secret (required)"
                  className="url-input"
                  disabled={!backendOnline}
                />
              </div>
              <small style={{ color: '#666', fontSize: '0.85rem', marginTop: '5px', display: 'block' }}>
                💡 <strong>Required:</strong> Both API Key and Secret are required. Placeholder values are not accepted.<br/>
                <strong>How it works:</strong> HMAC-SHA256 signature authentication used by Binance, OKX, and other crypto exchanges.<br/>
                <strong>Test URLs:</strong><br/>
                • Binance: <code>https://api.binance.com/api/v3/account</code> (requires valid API key/secret)<br/>
                • OKX: <code>https://www.okx.com/api/v5/account/balance</code> (requires valid API key/secret)<br/>
                <strong>💡 Tip:</strong> Don't have credentials? Switch to <strong>"None"</strong> or <strong>"Basic Auth"</strong> to test without real credentials!
              </small>
            </>
          )}

          {authentication === 'Bearer Token' && (
            <div className="input-group">
              <label>Bearer Token <span style={{ color: '#f44336' }}>*</span></label>
              <input
                type="password"
                value={bearerToken}
                onChange={(e) => setBearerToken(e.target.value)}
                placeholder="Enter your real bearer token (required)"
                className="url-input"
                disabled={!backendOnline}
              />
              <small style={{ color: '#666', fontSize: '0.85rem', marginTop: '5px', display: 'block' }}>
                💡 <strong>Required:</strong> You must enter a valid bearer token. Placeholder values are not accepted.<br/>
                <strong>How it works:</strong> Bearer token will be added to headers as <code>Authorization: Bearer YOUR_TOKEN</code>.<br/>
                <strong>Test URL:</strong> <code>https://httpbin.org/headers</code> - This endpoint shows all request headers, so you can verify your Bearer token is being sent correctly.<br/>
                <strong>💡 Tip:</strong> Use any token value (e.g., "test-token-123") with httpbin.org/headers to test - it will show your Bearer token in the response!<br/>
                <strong>Real APIs:</strong> GitHub, Twitter, and other OAuth 2.0 APIs use Bearer tokens (requires real tokens from those services).
              </small>
            </div>
          )}

          {authentication === 'Basic Auth' && (
            <>
              <div className="input-group">
                <label>Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g., admin, user, api_user"
                  className="url-input"
                  disabled={!backendOnline}
                />
              </div>
              <div className="input-group">
                <label>Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="url-input"
                  disabled={!backendOnline}
                />
              </div>
              <small style={{ color: '#666', fontSize: '0.85rem', marginTop: '5px', display: 'block' }}>
                💡 <strong>Example:</strong> Basic Auth encodes username:password in Base64 and adds to <code>Authorization: Basic BASE64_STRING</code> header.<br/>
                <strong>Test URLs:</strong><br/>
                • HTTPBin (public test): <code>https://httpbin.org/basic-auth/user/passwd</code> (use username: "user", password: "passwd")<br/>
                • Custom APIs: Any API that uses HTTP Basic Authentication<br/>
                <strong>Note:</strong> HTTPBin is a public testing service - perfect for testing Basic Auth without real credentials!
              </small>
            </>
          )}


          {connectorId && (
            <div className="input-group" style={{ 
              padding: '15px', 
              backgroundColor: '#e5e7eb',
              borderRadius: '5px',
              marginTop: '15px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong>Connector Status:</strong> {connectorStatus}
                  {connectorId && <div style={{ fontSize: '0.9em', color: '#666', marginTop: '5px' }}>
                    ID: {connectorId}
                  </div>}
                  {connectorStatus === 'running' && (
                    <div style={{ fontSize: '0.9em', color: '#666', marginTop: '5px' }}>
                      API: {wsConnected ? '✅ Connected' : '⏳ Connecting...'}
                    </div>
                  )}
                  {connectorId && (
                    <div style={{ marginTop: '10px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                      <button
                        onClick={() => fetchDataFromDatabase(connectorId)}
                        style={{
                          padding: '6px 12px',
                          backgroundColor: '#2196F3',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontSize: '0.9em'
                        }}
                      >
                        🔄 Refresh Data from Database
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            console.log('📊 Checking database count for connector:', connectorId)
                            const response = await fetch(`/api/connectors/${connectorId}/data?limit=5`)
                            const result = await response.json()
                            console.log('📊 Database check result:', result)
                            alert(`Total records in api_connector_data table: ${result.total}\nFetched in sample: ${result.count}\n\nNow fetching ALL data to display...`)
                            // Always fetch and display ALL data from api_connector_data table
                            console.log('🔄 Fetching ALL data from api_connector_data table...')
                            await fetchDataFromDatabase(connectorId)
                          } catch (err) {
                            console.error('❌ Error checking database:', err)
                            alert('Error checking database: ' + err.message)
                          }
                        }}
                        style={{
                          padding: '6px 12px',
                          backgroundColor: '#4CAF50',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontSize: '0.9em'
                        }}
                      >
                        📊 Check Database Count
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          <div className="button-group">
            {ingestionMode === 'Streaming' ? (
              <button 
                onClick={handleStartOrStopStream} 
                disabled={loading || !apiUrl || !backendOnline}
                className={connectorStatus === 'running' ? 'stop-button' : 'extract-button'}
                style={connectorStatus === 'running' ? {
                  backgroundColor: '#f44336',
                  color: 'white'
                } : {}}
              >
                {loading 
                  ? 'Creating Connector...' 
                  : connectorStatus === 'running'
                    ? 'Stop Streaming'
                    : 'Start Streaming'}
              </button>
            ) : (
              <button 
                onClick={handleExtract} 
                disabled={loading || !apiUrl || !backendOnline}
                className="extract-button"
              >
                {loading ? 'Extracting...' : 'Extract from API'}
              </button>
            )}
            {error && <div className="error-message" style={{ marginTop: '15px' }}>{error}</div>}
          </div>
            </div>
          </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default APISection
