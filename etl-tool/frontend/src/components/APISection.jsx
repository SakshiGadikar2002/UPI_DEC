import { useState, useEffect, useRef } from 'react'
import './Section.css'
import { checkBackendHealth } from '../utils/backendCheck'
import { removeDuplicates } from '../utils/duplicateRemover'
import { getRealtimeWebSocket } from '../utils/realtimeWebSocket'

function APISection({ data, setData }) {
  const [apiUrl, setApiUrl] = useState('https://api.binance.com/api/v3/depth?symbol=BTCUSDT')
  const [httpMethod, setHttpMethod] = useState('GET')
  const [headers, setHeaders] = useState('{"Authorization": "Bearer token"}\n\nAuthorization: Bearer token')
  const [queryParams, setQueryParams] = useState('{"limit": 100, "page": 1}\n\nlimit=100&page=1')
  const [authentication, setAuthentication] = useState('None')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [bearerToken, setBearerToken] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [ingestionMode, setIngestionMode] = useState('Real-Time Streaming (New)')
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
  const wsRef = useRef(null)
  const dataRef = useRef([])
  const lastUpdateTimeRef = useRef(0) // Track last update time for debouncing
  const lastStateDataRef = useRef(null) // Track last state data to prevent unnecessary updates

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
        setError('Backend server is not running. Please start the backend server at http://localhost:8000')
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
      
      // Then refresh every 10 seconds to get latest data from api_connector_data table
      // Increased interval significantly to reduce flickering
      const interval = setInterval(() => {
        console.log('🔄 Auto-refreshing from api_connector_data table...')
        fetchDataFromDatabase(connectorId)
      }, 10000) // Refresh every 10 seconds to minimize flickering
      
      return () => {
        console.log('🔄 Clearing auto-refresh interval')
        clearInterval(interval)
      }
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

  const fetchDataFromDatabase = async (connectorIdToFetch = null) => {
    const idToUse = connectorIdToFetch || connectorId
    if (!idToUse) {
      console.log('❌ No connector ID to fetch data for')
      return
    }
    
    console.log(`🔄 Fetching data from api_connector_data table for connector: ${idToUse}`)
    
    try {
      const url = `http://localhost:8000/api/connectors/${idToUse}/data?limit=1000&sort_by=timestamp&sort_order=-1`
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
      setError('Backend server is not running. Please start the backend server at http://localhost:8000')
      setBackendOnline(false)
      return
    }
    setBackendOnline(true)

    setLoading(true)
    setError(null)

    try {
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
      
      // Add credentials based on auth type
      if (authentication === 'API Key' && apiKey) {
        connectorData.api_key = apiKey
      } else if (authentication === 'HMAC' && apiKey && apiSecret) {
        connectorData.api_key = apiKey
        connectorData.api_secret = apiSecret
      } else if (authentication === 'Bearer Token' && bearerToken) {
        connectorData.bearer_token = bearerToken
      } else if (authentication === 'Basic Auth' && username && password) {
        connectorData.username = username
        connectorData.password = password
      }

      // Create connector
      const createResponse = await fetch('http://localhost:8000/api/connectors', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(connectorData)
      })

      if (!createResponse.ok) {
        const errorData = await createResponse.json()
        throw new Error(errorData.detail || 'Failed to create connector')
      }

      const connector = await createResponse.json()
      setConnectorId(connector.connector_id)

      // If real-time streaming, start the connector
      if (ingestionMode === 'Real-Time Streaming (New)') {
        const startResponse = await fetch(`http://localhost:8000/api/connectors/${connector.connector_id}/start`, {
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
      const response = await fetch(`http://localhost:8000/api/connectors/${connectorId}/stop`, {
        method: 'POST'
      })
      
      if (response.ok) {
        setConnectorStatus('stopped')
        setWsConnected(false)
        // Disconnect WebSocket
        if (wsRef.current) {
          wsRef.current.disconnect()
          wsRef.current = null
        }
      }
    } catch (err) {
      setError(`Error stopping connector: ${err.message}`)
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
        {/* Quick Connect Section - Collapsible */}
        {quickConnectExpanded && (
          <div className="quick-connect-section">
            <div className="quick-connect-header">
              <h3>
                <span className="rocket-icon">🚀</span>
                Quick Connect - Real-Time Crypto Data
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
        <div className="manual-api-config">
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

          <div className="input-group">
            <label>Authentication</label>
            <select
              value={authentication}
              onChange={(e) => setAuthentication(e.target.value)}
              className="url-input"
              disabled={!backendOnline}
            >
              <option value="None">None</option>
              <option value="API Key">API Key</option>
              <option value="HMAC">HMAC</option>
              <option value="Bearer Token">Bearer Token</option>
              <option value="Basic Auth">Basic Auth</option>
            </select>
          </div>

          {authentication === 'API Key' && (
            <div className="input-group">
              <label>API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your API key"
                className="url-input"
                disabled={!backendOnline}
              />
            </div>
          )}

          {authentication === 'HMAC' && (
            <>
              <div className="input-group">
                <label>API Key</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter your API key"
                  className="url-input"
                  disabled={!backendOnline}
                />
              </div>
              <div className="input-group">
                <label>API Secret</label>
                <input
                  type="password"
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  placeholder="Enter your API secret"
                  className="url-input"
                  disabled={!backendOnline}
                />
              </div>
            </>
          )}

          {authentication === 'Bearer Token' && (
            <div className="input-group">
              <label>Bearer Token</label>
              <input
                type="password"
                value={bearerToken}
                onChange={(e) => setBearerToken(e.target.value)}
                placeholder="Enter your bearer token"
                className="url-input"
                disabled={!backendOnline}
              />
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
                  placeholder="Enter username"
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
                  placeholder="Enter password"
                  className="url-input"
                  disabled={!backendOnline}
                />
              </div>
            </>
          )}

          <div className="input-group">
            <label>Ingestion Mode</label>
            <select
              value={ingestionMode}
              onChange={(e) => setIngestionMode(e.target.value)}
              className="url-input"
              disabled={!backendOnline}
            >
              <option value="Real-Time Streaming (New)">Real-Time Streaming (New)</option>
              <option value="One-Time Fetch">One-Time Fetch</option>
            </select>
            {ingestionMode === 'Real-Time Streaming (New)' && (
              <>
                <p className="ingestion-hint">Streams data continuously to database and UI.</p>
                <div style={{ marginTop: '10px' }}>
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
              </>
            )}
          </div>

          {connectorId && (
            <div className="input-group" style={{ 
              padding: '15px', 
              backgroundColor: connectorStatus === 'running' ? '#e8f5e9' : '#fff3e0',
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
                      WebSocket: {wsConnected ? '✅ Connected' : '⏳ Connecting...'}
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
                            const response = await fetch(`http://localhost:8000/api/connectors/${connectorId}/data?limit=5`)
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
                {connectorStatus === 'running' && (
                  <button
                    onClick={handleStopConnector}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: '#f44336',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    Stop Connector
                  </button>
                )}
              </div>
            </div>
          )}

          <div className="button-group">
            <button 
              onClick={handleExtract} 
              disabled={loading || !apiUrl || !backendOnline}
              className="extract-button"
            >
              {loading 
                ? 'Creating Connector...' 
                : ingestionMode === 'Real-Time Streaming (New)' 
                  ? 'Start Real-Time Stream' 
                  : 'Extract from API'}
            </button>
            {error && <div className="error-message" style={{ marginTop: '15px' }}>{error}</div>}
          </div>
        </div>
      </div>
    </div>
  )
}

export default APISection
