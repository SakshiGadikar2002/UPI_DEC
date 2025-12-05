import { useState, useEffect, useRef } from 'react'
import './Section.css'
import { checkBackendHealth } from '../utils/backendCheck'
import { removeDuplicates } from '../utils/duplicateRemover'
import { OKX_CONFIG, BINANCE_CONFIG } from '../utils/websocketConfig'
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts'
import RealtimeStream from './RealtimeStream'

function WebSocketSection({ data, setData }) {
  const [wsUrl, setWsUrl] = useState('')
  const [subscriptionMessage, setSubscriptionMessage] = useState('')
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const [messages, setMessages] = useState([])
  const [backendOnline, setBackendOnline] = useState(false)
  const [checkingBackend, setCheckingBackend] = useState(true)
  const [exchange, setExchange] = useState('custom') // 'okx', 'binance', 'custom'
  const [okxChannel, setOkxChannel] = useState('trades')
  const [okxInstId, setOkxInstId] = useState('ALL') // Default to ALL instruments
  const [binanceSymbol, setBinanceSymbol] = useState('ALL') // Default to ALL instruments
  const [binanceStreamType, setBinanceStreamType] = useState('trade')
  const [dataFormat, setDataFormat] = useState(null)
  const [connectionTime, setConnectionTime] = useState(null)
  const [firstMessageTime, setFirstMessageTime] = useState(null)
  const [currentMessageRate, setCurrentMessageRate] = useState(0)
  const [uptime, setUptime] = useState(0)
  const [showCharts, setShowCharts] = useState(false)
  const [showDashboard, setShowDashboard] = useState(false) // Toggle dashboard view
  const [activeView, setActiveView] = useState('stream') // 'stream' or 'dashboard'
  const [isRealtime, setIsRealtime] = useState(false) // Track if WebSocket is real-time
  const messageTimestampsRef = useRef([]) // Track message timestamps for real-time detection
  const [throughputData, setThroughputData] = useState([]) // Messages per second over time
  const [latencyData, setLatencyData] = useState([]) // Latency per message
  const [scalabilityData, setScalabilityData] = useState([]) // Cumulative metrics
  const [saveToPostgres, setSaveToPostgres] = useState(true) // Always enabled - PostgreSQL saving
  const [postgresConnected, setPostgresConnected] = useState(false) // PostgreSQL connection status
  const [postgresSaveCount, setPostgresSaveCount] = useState(0) // Count of saved batches
  const [lastPostgresSaveTime, setLastPostgresSaveTime] = useState(null) // Last save timestamp
  const messageBufferRef = useRef([]) // Buffer messages for batch saving
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const pingIntervalRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)
  const maxReconnectAttempts = 999999 // Essentially unlimited
  const reconnectDelayRef = useRef(1000) // Start with 1 second
  const isManualDisconnectRef = useRef(false) // Track if user manually disconnected
  const connectionHealthCheckRef = useRef(null)
  const messageCountRef = useRef(0)
  const startTimeRef = useRef(null)
  const messagesPerSecondRef = useRef(0)
  const lastSecondRef = useRef(Date.now())
  const messageCountLastSecondRef = useRef(0)

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

  // Check PostgreSQL connection status
  useEffect(() => {
    const checkPostgres = async () => {
      if (!backendOnline) {
        setPostgresConnected(false)
        return
      }
      try {
        const response = await fetch('/api/postgres/status')
        const data = await response.json()
        setPostgresConnected(data.status === 'connected')
      } catch (error) {
        setPostgresConnected(false)
      }
    }
    
    checkPostgres()
    const interval = setInterval(checkPostgres, 5000) // Check every 5 seconds
    return () => clearInterval(interval)
  }, [backendOnline])

  // Always enable PostgreSQL saving when connected
  useEffect(() => {
    if (postgresConnected && connected) {
      // Always enable saving when PostgreSQL is connected and WebSocket is active
      setSaveToPostgres(true)
    }
  }, [postgresConnected, connected])

  // Function to save individual message in real-time
  const saveIndividualMessage = async (message) => {
    if (!postgresConnected) return
    
    try {
      const messageData = {
        timestamp: message.timestamp?.toISOString() || new Date().toISOString(),
        exchange: exchange,
        type: message.type || 'trade',
        data: message.data, // Complete raw data
        messageNumber: message.messageNumber,
        format: message.format,
        totalTime: message.totalTime,
        extractTime: message.extractTime,
        transformTime: message.transformTime,
        loadTime: message.loadTime
      }

      // Save immediately (fire and forget - don't wait for response)
      fetch('/api/websocket/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(messageData)
      }).catch(error => {
        // Silently handle errors to not block the UI
        console.error('Error saving individual message:', error)
      })
    } catch (error) {
      console.error('Error preparing message for save:', error)
    }
  }

  // Save messages to PostgreSQL in batches (auto-save when connected)
  useEffect(() => {
    if (!postgresConnected || !saveToPostgres) return

    const saveBatch = async () => {
      if (messageBufferRef.current.length === 0) return
      
      const batch = messageBufferRef.current.splice(0, 50) // Save 50 messages at a time

      try {
        const batchData = {
          timestamp: new Date().toISOString(),
          exchange: exchange,
          total_messages: batch.length,
          messages_per_second: currentMessageRate,
          instruments: [...new Set(batch.map(m => {
            if (m.data?.arg?.instId) return m.data.arg.instId
            if (m.data?.stream) return m.data.stream.split('@')[0]
            return null
          }).filter(Boolean))],
          messages: batch.map(m => ({
            timestamp: m.timestamp?.toISOString() || new Date().toISOString(),
            exchange: exchange,
            data: m.data,
            message_type: m.type || 'trade',
            latency_ms: m.totalTime ? m.totalTime * 1000 : null
          })),
          metrics: {
            avg_latency: latencyData.length > 0 
              ? latencyData.reduce((sum, l) => sum + (l.latency || 0), 0) / latencyData.length 
              : 0,
            throughput: currentMessageRate,
            total_messages: messageCountRef.current
          }
        }

        const response = await fetch('/api/websocket/save-batch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(batchData)
        })
        
        if (response.ok) {
          const result = await response.json()
          setPostgresSaveCount(prev => prev + 1)
          setLastPostgresSaveTime(new Date().toLocaleTimeString())
          console.log(`✅ Saved ${batch.length} messages to PostgreSQL. Total batches: ${postgresSaveCount + 1}`)
        } else {
          console.error('Error saving to PostgreSQL:', await response.text())
        }
      } catch (error) {
        console.error('Error saving to PostgreSQL:', error)
      }
    }

    // Save every 5 seconds or when buffer reaches 50 messages
    const interval = setInterval(() => {
      if (messageBufferRef.current.length >= 50) {
        saveBatch()
      }
    }, 5000)

    // Also save when buffer is full immediately
    if (messageBufferRef.current.length >= 50) {
      saveBatch()
    }

    return () => clearInterval(interval)
  }, [postgresConnected, exchange, currentMessageRate, latencyData])

  const connectWebSocket = async () => {
    // Check backend before proceeding
    const isOnline = await checkBackendHealth()
    if (!isOnline) {
      setError('Backend server is not running. Please start the backend server.')
      setBackendOnline(false)
      return
    }
    setBackendOnline(true)

    // Close existing connection if any
    if (wsRef.current) {
      try {
        if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
          wsRef.current.close()
        }
      } catch (e) {
        console.error('Error closing existing connection:', e)
      }
      wsRef.current = null
    }

    // Clear any pending reconnection
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    setError(null)
    setMessages([])
    setData(null) // Clear previous data for fresh start
    setDataFormat(null)
    setConnectionTime(null)
    setFirstMessageTime(null)
    setThroughputData([])
    setLatencyData([])
    setScalabilityData([])
    messageCountRef.current = 0
    startTimeRef.current = Date.now()
    setConnectionTime(Date.now())
    lastSecondRef.current = Date.now()
    messageCountLastSecondRef.current = 0
    messagesPerSecondRef.current = 0
    
    let finalWsUrl = wsUrl.trim()
    let finalSubMsg = subscriptionMessage.trim()
    
    // Auto-configure for OKX
    if (exchange === 'okx') {
      finalWsUrl = OKX_CONFIG.WS_URL
      const subscribeMsg = OKX_CONFIG.createSubscribeMessage(okxChannel, okxInstId)
      finalSubMsg = JSON.stringify(subscribeMsg)
      setWsUrl(finalWsUrl)
      setSubscriptionMessage(finalSubMsg)
      console.log('OKX WebSocket URL:', finalWsUrl)
      console.log('OKX Channel:', okxChannel, 'Instrument ID:', okxInstId)
      if (okxInstId === 'ALL') {
        console.log('Subscribing to all OKX instruments')
      }
    }
    // Auto-configure for Binance
    else if (exchange === 'binance') {
      const streamName = BINANCE_CONFIG.createStreamName(binanceSymbol, binanceStreamType)
      if (binanceSymbol === 'ALL') {
        // For multiple streams, use the combined stream endpoint
        finalWsUrl = `wss://stream.binance.com:9443/stream?streams=${streamName}`
      } else {
        finalWsUrl = `${BINANCE_CONFIG.WS_URL}${streamName}`
      }
      finalSubMsg = '' // Binance doesn't need subscription message
      setWsUrl(finalWsUrl)
      setSubscriptionMessage('')
      console.log('Binance WebSocket URL:', finalWsUrl)
      console.log('Binance Symbol:', binanceSymbol, 'Stream Type:', binanceStreamType)
      if (binanceSymbol === 'ALL') {
        console.log('Subscribing to all Binance symbols')
      }
    }
    // Custom WebSocket
    else {
      if (!finalWsUrl) {
        setError('Please enter a WebSocket URL or select OKX/Binance')
        return
      }
      // Validate WebSocket URL format
      if (!finalWsUrl.startsWith('ws://') && !finalWsUrl.startsWith('wss://')) {
        setError('WebSocket URL must start with ws:// or wss://')
        return
      }
      console.log('Custom WebSocket URL:', finalWsUrl)
      if (finalSubMsg) {
        console.log('Custom subscription message:', finalSubMsg)
      }
    }
    
    try {
      const ws = new WebSocket(finalWsUrl)
      wsRef.current = ws
      
      // Set up ping/pong for Binance to keep connection alive
      if (exchange === 'binance') {
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            try {
              // Binance WebSocket doesn't require explicit ping, but we can log connection status
              console.log('Binance connection alive')
            } catch (e) {
              console.error('Error checking connection:', e)
            }
          }
        }, 30000) // Check connection every 30 seconds
      }

      ws.onopen = () => {
        console.log('WebSocket connected successfully')
        const connectTime = Date.now()
        const loadTime = connectionTime ? ((connectTime - connectionTime) / 1000).toFixed(3) : '0.000'
        setConnected(true)
        setError(null)
        setIsRealtime(false) // Reset real-time detection
        messageTimestampsRef.current = [] // Reset message timestamps
        
        // Reset reconnection attempts on successful connection
        reconnectAttemptsRef.current = 0
        reconnectDelayRef.current = 1000
        
        // Set up connection health monitoring
        if (connectionHealthCheckRef.current) {
          clearInterval(connectionHealthCheckRef.current)
        }
        
        // Track last message time for health monitoring
        const lastMessageTimeRef = { current: Date.now() }
        connectionHealthCheckRef.current = setInterval(() => {
          const now = Date.now()
          const timeSinceLastMessage = now - lastMessageTimeRef.current
          
          // If no messages for 60 seconds, connection might be dead
          if (timeSinceLastMessage > 60000 && ws.readyState === WebSocket.OPEN) {
            console.warn('⚠️ No messages received for 60 seconds. Connection might be dead.')
            // Try to ping the connection
            try {
              if (exchange === 'okx') {
                ws.send(JSON.stringify({"op": "ping"}))
              }
            } catch (e) {
              console.error('Error sending ping:', e)
            }
          }
        }, 30000) // Check every 30 seconds
        
        // Store lastMessageTimeRef in ws object for access in onmessage
        ws._lastMessageTimeRef = lastMessageTimeRef
        
        const systemMsg = {
          type: 'system', 
          message: `✅ Connected to WebSocket successfully`, 
          timestamp: new Date(),
          extractTime: parseFloat(loadTime),
          transformTime: 0,
          loadTime: 0,
          totalTime: parseFloat(loadTime)
        }
        setMessages(prev => [systemMsg, ...prev])
        
        // Send subscription message if provided
        if (finalSubMsg) {
          try {
            const parsedSubMsg = JSON.parse(finalSubMsg)
            const messageToSend = JSON.stringify(parsedSubMsg)
            console.log('Sending subscription:', messageToSend)
            ws.send(messageToSend)
            const subMsg = {
              type: 'system', 
              message: '📤 Subscription message sent', 
              timestamp: new Date(),
              sentData: parsedSubMsg,
              extractTime: 0,
              transformTime: 0,
              loadTime: 0,
              totalTime: 0
            }
            setMessages(prev => [subMsg, ...prev])
          } catch (parseError) {
            console.error('Error parsing subscription message:', parseError)
            setError(`Invalid JSON in subscription message: ${parseError.message}`)
            // Still try to send as string
            ws.send(finalSubMsg)
            const subMsgStr = {
              type: 'system', 
              message: '📤 Subscription message sent (as string)', 
              timestamp: new Date(),
              extractTime: 0,
              transformTime: 0,
              loadTime: 0,
              totalTime: 0
            }
            setMessages(prev => [subMsgStr, ...prev])
          }
        } else {
          const systemMsg = {
            type: 'system', 
            message: exchange === 'custom'
              ? '✅ Connected - waiting for data... (Auto-detecting real-time mode)'
              : exchange !== 'binance' 
                ? '⚠️ No subscription message provided - waiting for data...'
                : '✅ Connected to Binance - receiving data...', 
            timestamp: new Date(),
            extractTime: 0,
            transformTime: 0,
            loadTime: 0,
            totalTime: 0
          }
          setMessages(prev => [systemMsg, ...prev])
        }
      }

      // Define message handler function
      const handleWebSocketMessage = (parsedData, messageReceivedTime) => {
        // Update message rate tracking
        const now = messageReceivedTime || Date.now()
        
        // Update last message time for health monitoring
        if (ws._lastMessageTimeRef) {
          ws._lastMessageTimeRef.current = now
        }
        
        messageCountRef.current++
        
        // Track message timestamps for real-time detection
        messageTimestampsRef.current.push(now)
        // Keep only last 10 timestamps for detection
        if (messageTimestampsRef.current.length > 10) {
          messageTimestampsRef.current.shift()
        }
        
        // Detect if this is a real-time stream (messages coming frequently)
        if (messageTimestampsRef.current.length >= 3 && exchange === 'custom') {
          const recentTimestamps = messageTimestampsRef.current.slice(-3)
          const timeDiffs = []
          for (let i = 1; i < recentTimestamps.length; i++) {
            timeDiffs.push(recentTimestamps[i] - recentTimestamps[i - 1])
          }
          const avgTimeDiff = timeDiffs.reduce((a, b) => a + b, 0) / timeDiffs.length
          // If average time between messages is less than 5 seconds, it's likely real-time
          if (avgTimeDiff < 5000 && !isRealtime) {
            setIsRealtime(true)
            const realtimeMsg = {
              type: 'system',
              message: '🔄 Real-time stream detected! Continuous data flow enabled.',
              timestamp: new Date(),
              extractTime: 0,
              transformTime: 0,
              loadTime: 0,
              totalTime: 0
            }
            setMessages(prev => [realtimeMsg, ...prev])
          }
        }
        
        // Track first message time
        if (!firstMessageTime) {
          setFirstMessageTime(now)
        }
        
        // Measure timing - start from message arrival
        const messageStartTime = performance.now()
        
        // Detect data format with enhanced detection for custom WebSockets
        let detectedFormat = 'Unknown'
        if (parsedData && parsedData.arg && parsedData.data) {
          detectedFormat = 'OKX'
        } else if (parsedData && parsedData.stream && parsedData.data) {
          detectedFormat = 'Binance (Stream)'
        } else if (parsedData && parsedData.e && (parsedData.e === 'trade' || parsedData.e === '24hrTicker' || parsedData.e === 'depthUpdate')) {
          detectedFormat = 'Binance (Direct)'
        } else if (parsedData && parsedData.type && parsedData.channel) {
          detectedFormat = 'Coinbase Pro'
        } else if (parsedData && parsedData.channel && parsedData.data) {
          detectedFormat = 'Generic Channel Format'
        } else if (parsedData && parsedData.event) {
          detectedFormat = 'Event-Based Format'
        } else if (parsedData && parsedData.topic) {
          detectedFormat = 'Topic-Based Format'
        } else if (Array.isArray(parsedData)) {
          detectedFormat = 'Array'
        } else if (typeof parsedData === 'object' && parsedData !== null) {
          // Check for common real-time data patterns
          if (parsedData.price || parsedData.timestamp || parsedData.time || parsedData.data) {
            detectedFormat = 'Real-time Data Object'
          } else {
            detectedFormat = 'JSON Object'
          }
        } else {
          detectedFormat = typeof parsedData
        }
        if (!dataFormat || dataFormat !== detectedFormat) {
          setDataFormat(detectedFormat)
        }
        
        // Calculate messages per second and update throughput data
        if (now - lastSecondRef.current >= 1000) {
          const messagesPerSec = messageCountLastSecondRef.current
          messagesPerSecondRef.current = messagesPerSec
          setCurrentMessageRate(messagesPerSec)
          
          // Update throughput data (messages per second over time)
          setThroughputData(prev => {
            const newData = [...prev, {
              time: now,
              throughput: messagesPerSec,
              exchange: exchange
            }]
            // Keep last 60 data points (1 minute at 1 second intervals)
            return newData.slice(-60)
          })
          
          messageCountLastSecondRef.current = 1
          lastSecondRef.current = now
        } else {
          messageCountLastSecondRef.current++
        }

        // Calculate timing metrics
        // Extract: Time from connection to message arrival
        const extractTime = connectionTime ? ((now - connectionTime) / 1000) : 0
        
        // Transform: Time to process/parse the message (minimal for WebSocket)
        const transformEndTime = performance.now()
        const transformTime = (transformEndTime - messageStartTime) / 1000
        
        // Load: Time to update state (will be measured after state update)
        const loadTime = 0.001 // Minimal load time for WebSocket

        const totalLatency = extractTime + transformTime + loadTime
        
        const newMessage = {
          type: 'data',
          data: parsedData,
          timestamp: new Date(now),
          format: detectedFormat,
          messageNumber: messageCountRef.current,
          extractTime: extractTime,
          transformTime: transformTime,
          loadTime: loadTime,
          totalTime: totalLatency,
          exchange: exchange
        }

        // Save individual message to PostgreSQL in real-time (always enabled)
        if (postgresConnected && saveToPostgres) {
          // Save immediately (real-time) - fire and forget
          saveIndividualMessage(newMessage)
          
          // Also add to buffer for batch saving
          messageBufferRef.current.push(newMessage)
        }
        
        // Compute new latency data (latency per message) - compute before state update
        const newLatencyEntry = {
          time: now,
          latency: totalLatency * 1000, // Convert to milliseconds
          messageNumber: messageCountRef.current,
          exchange: exchange
        }
        const newLatencyData = [...latencyData, newLatencyEntry].slice(-100)
        
        // Update latency data state
        setLatencyData(newLatencyData)
        
        // Update scalability data (cumulative metrics)
        setScalabilityData(prev => {
          const totalMessages = messageCountRef.current
          const avgLatency = prev.length > 0 
            ? (prev[prev.length - 1].avgLatency * (prev.length - 1) + totalLatency * 1000) / prev.length
            : totalLatency * 1000
          
          const newData = [...prev, {
            time: now,
            totalMessages: totalMessages,
            avgLatency: avgLatency,
            currentThroughput: messagesPerSecondRef.current,
            exchange: exchange
          }]
          // Keep last 60 data points
          return newData.slice(-60)
        })

        // Compute new throughput data if needed - use current state value
        let newThroughputData = throughputData
        if (now - lastSecondRef.current >= 1000) {
          newThroughputData = [...throughputData, {
            time: now,
            throughput: messageCountLastSecondRef.current,
            exchange: exchange
          }].slice(-60)
        }

        setMessages(prev => {
          // Add new message at the beginning (newest first)
          const updatedMessages = [newMessage, ...prev]
          
          // For WebSocket, handle different data structures from various APIs
          setData(prevData => {
            let newDataArray = []
            let transformedCount = 0
            
            // Handle OKX format: { "arg": {...}, "data": [...] }
            // OKX sends subscription confirmations with "event" field, but actual data has "arg" and "data"
            if (parsedData && parsedData.data && Array.isArray(parsedData.data) && parsedData.arg) {
              // This is OKX trade data format - has both "arg" and "data"
              transformedCount = parsedData.data.length
              if (prevData && prevData.data && Array.isArray(prevData.data)) {
                newDataArray = [...prevData.data, ...parsedData.data]
              } else {
                newDataArray = parsedData.data
              }
            }
            // Handle generic format with data array (but no arg field)
            else if (parsedData && parsedData.data && Array.isArray(parsedData.data)) {
              transformedCount = parsedData.data.length
              if (prevData && prevData.data && Array.isArray(prevData.data)) {
                newDataArray = [...prevData.data, ...parsedData.data]
              } else {
                newDataArray = parsedData.data
              }
            }
            // Handle Binance format: { "stream": "...", "data": {...} }
            else if (parsedData && parsedData.stream && parsedData.data) {
              transformedCount = 1
              const tradeData = { ...parsedData.data, stream: parsedData.stream }
              if (prevData && prevData.data && Array.isArray(prevData.data)) {
                newDataArray = [...prevData.data, tradeData]
              } else {
                newDataArray = [tradeData]
              }
            }
            // Handle Binance direct trade format: { "e": "trade", "s": "BTCUSDT", "p": "50000", ... }
            else if (parsedData && parsedData.e === 'trade' && parsedData.s) {
              transformedCount = 1
              if (prevData && prevData.data && Array.isArray(prevData.data)) {
                newDataArray = [...prevData.data, parsedData]
              } else {
                newDataArray = [parsedData]
              }
            }
            // Handle Coinbase format: array of objects
            else if (Array.isArray(parsedData)) {
              transformedCount = parsedData.length
              if (prevData && prevData.data && Array.isArray(prevData.data)) {
                newDataArray = [...prevData.data, ...parsedData]
              } else {
                newDataArray = parsedData
              }
            }
            // Handle single object (trade, ticker, etc.)
            else if (parsedData && typeof parsedData === 'object' && parsedData !== null) {
              // Skip subscription confirmations (OKX sends these with "event" field)
              if (parsedData.event === 'subscribe' || parsedData.event === 'unsubscribe') {
                return prevData || {
                  source: 'WebSocket',
                  url: wsUrl,
                  mode: 'Realtime',
                  data: [],
                  totalMessages: messageCountRef.current,
                  messagesPerSecond: messagesPerSecondRef.current,
                  transformed: prevData?.transformed || 0,
                  timestamp: new Date().toISOString()
                }
              }
              
              // Handle Binance direct trade data (without stream wrapper)
              // Binance sometimes sends data directly as { "e": "trade", "s": "BTCUSDT", ... }
              if (parsedData.e && (parsedData.e === 'trade' || parsedData.e === '24hrTicker' || parsedData.e === 'depthUpdate')) {
                transformedCount = 1
                if (prevData && prevData.data && Array.isArray(prevData.data)) {
                  newDataArray = [...prevData.data, parsedData]
                } else {
                  newDataArray = [parsedData]
                }
              }
              // Check if it's a trade object (common fields)
              else if (parsedData.price || parsedData.size || parsedData.amount || 
                                 parsedData.quantity || parsedData.trade_id || parsedData.id ||
                                 parsedData.px || parsedData.sz || parsedData.tradeId ||
                                 parsedData.s || parsedData.p || parsedData.q) {
                transformedCount = 1
                if (prevData && prevData.data && Array.isArray(prevData.data)) {
                  newDataArray = [...prevData.data, parsedData]
                } else {
                  newDataArray = [parsedData]
                }
              } else {
                // Unknown object format, still add it (might be Binance data in different format)
                transformedCount = 1
                if (prevData && prevData.data && Array.isArray(prevData.data)) {
                  newDataArray = [...prevData.data, parsedData]
                } else {
                  newDataArray = [parsedData]
                }
              }
            }
            // Handle string or primitive values
            else {
              transformedCount = 1
              if (prevData && prevData.data && Array.isArray(prevData.data)) {
                newDataArray = [...prevData.data, { value: parsedData, timestamp: new Date().toISOString() }]
              } else {
                newDataArray = [{ value: parsedData, timestamp: new Date().toISOString() }]
              }
            }
            
            // Remove duplicates periodically (every 100 items or when array gets large)
            let finalDataArray = newDataArray
            let duplicateCount = prevData?.duplicateCount || 0
            
            if (newDataArray.length > 0 && (newDataArray.length % 100 === 0 || newDataArray.length > 1000)) {
              const { uniqueData, duplicateCount: newDuplicates } = removeDuplicates(newDataArray)
              duplicateCount += newDuplicates
              finalDataArray = uniqueData
            }
            
            // Limit array size to prevent memory issues (keep last 1000 items)
            if (finalDataArray.length > 1000) {
              finalDataArray = finalDataArray.slice(-1000)
            }
            
            const totalTransformed = (prevData?.transformed || 0) + transformedCount
            const totalRows = (prevData?.totalRows || 0) + transformedCount
            
            // Collect timing data for charts (last 50 messages)
            const dataMessages = updatedMessages.filter(m => m.type === 'data')
            const timingData = dataMessages
              .slice(0, 50) // Keep last 50 for charts
              .map(m => ({
                time: m.timestamp.getTime(),
                extract: m.extractTime || 0,
                transform: m.transformTime || 0,
                load: m.loadTime || 0,
                total: m.totalTime || 0
              }))
            
            return {
              source: 'WebSocket',
              url: wsUrl,
              mode: isRealtime || exchange !== 'custom' ? 'Realtime' : 'Stream',
              data: finalDataArray,
              totalRows: totalRows,
              duplicateCount: duplicateCount,
              totalMessages: messageCountRef.current,
              messagesPerSecond: messagesPerSecondRef.current,
              transformed: totalTransformed,
              timestamp: new Date().toISOString(),
              messages: updatedMessages, // Pass messages to DataDisplay
              dataFormat: detectedFormat,
              connectionTime: connectionTime,
              firstMessageTime: firstMessageTime,
              currentMessageRate: currentMessageRate,
              uptime: uptime,
              timingData: timingData,
              isRealtime: isRealtime || exchange !== 'custom',
              latencyData: newLatencyData, // Include for Visualization section (use computed new value)
              throughputData: newThroughputData, // Include for Visualization section (use computed new value)
              exchange: exchange // Include exchange type
            }
          })
          
          return updatedMessages
        })
      }

      ws.onmessage = (event) => {
        try {
          const messageReceivedTime = Date.now()
          
          // Update last message time for health monitoring
          if (connectionHealthCheckRef.current) {
            // This will be checked by the health monitor
          }
          
          let parsedData = null
          let rawData = event.data
          
          // Handle OKX pong response first (before parsing as data)
          if (exchange === 'okx') {
            try {
              const pongCheck = JSON.parse(rawData)
              if (pongCheck.event === 'pong') {
                console.log('OKX pong received - connection healthy')
                return // Don't process pong as a data message
              }
            } catch (e) {
              // Not a pong, continue with normal processing
            }
          }
          
          // Handle different data types
          if (typeof rawData === 'string') {
            try {
              parsedData = JSON.parse(rawData)
              
              // Handle Binance ping response
              if (exchange === 'binance' && parsedData.result === null && parsedData.id) {
                // This is a ping/pong response, ignore it
                return
              }
              
              // Log for debugging (especially for custom WebSockets)
              if (exchange === 'custom') {
                console.log('Custom WebSocket message received:', parsedData)
              } else if (exchange === 'binance') {
                console.log('Binance message received:', parsedData)
              }
            } catch (parseErr) {
              // Try to handle non-JSON strings (might be plain text or other format)
              console.warn('Failed to parse as JSON:', parseErr, rawData)
              // Try to extract useful data from string
              if (typeof rawData === 'string' && rawData.length > 0) {
                parsedData = { 
                  raw: rawData, 
                  format: 'text',
                  timestamp: new Date().toISOString()
                }
              } else {
                parsedData = rawData
              }
            }
          } else if (rawData instanceof Blob) {
            // Handle binary data
            rawData.text().then(text => {
              try {
                const parsed = JSON.parse(text)
                handleWebSocketMessage(parsed, messageReceivedTime)
              } catch {
                handleWebSocketMessage({ 
                  value: text, 
                  format: 'binary',
                  timestamp: new Date().toISOString()
                }, messageReceivedTime)
              }
            })
            return
          } else if (rawData instanceof ArrayBuffer) {
            // Handle ArrayBuffer
            try {
              const text = new TextDecoder().decode(rawData)
              const parsed = JSON.parse(text)
              handleWebSocketMessage(parsed, messageReceivedTime)
            } catch {
              handleWebSocketMessage({ 
                value: 'ArrayBuffer data',
                format: 'binary',
                timestamp: new Date().toISOString()
              }, messageReceivedTime)
            }
            return
          } else {
            parsedData = rawData
          }

          handleWebSocketMessage(parsedData, messageReceivedTime)
        } catch (err) {
          console.error('Error parsing WebSocket message:', err)
          setError(`Error processing message: ${err.message}`)
        }
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket error event:', error)
        if (exchange === 'binance') {
          console.error('Binance WebSocket error - check URL format and connection')
          setError('Binance WebSocket connection error. Please check the URL and try again.')
        }
        // Don't set error state here for other exchanges - let onclose handle it
        // This prevents showing errors before connection attempt completes
      }

      ws.onclose = (event) => {
        // Clear ping interval if it exists
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current)
          pingIntervalRef.current = null
        }
        
        // Clear health check
        if (connectionHealthCheckRef.current) {
          clearInterval(connectionHealthCheckRef.current)
          connectionHealthCheckRef.current = null
        }
        
        wsRef.current = null
        
        // If user manually disconnected, don't reconnect
        if (isManualDisconnectRef.current) {
          setConnected(false)
          isManualDisconnectRef.current = false
          return
        }
        
        const closeReason = event.code === 1000 ? 'Normal closure' : 
                           event.code === 1001 ? 'Going away' :
                           event.code === 1002 ? 'Protocol error' :
                           event.code === 1003 ? 'Unsupported data' :
                           event.code === 1006 ? 'Abnormal closure' :
                           event.code === 1011 ? 'Server error' : 
                           event.code === 1005 ? 'No status received' : `Code: ${event.code}`
        
        // Auto-reconnect logic
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++
          
          // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
          const delay = Math.min(reconnectDelayRef.current * Math.pow(2, reconnectAttemptsRef.current - 1), 30000)
          
          const reconnectMsg = {
            type: 'system', 
            message: `Connection lost. Reconnecting in ${Math.round(delay/1000)}s... (Attempt ${reconnectAttemptsRef.current})`, 
            timestamp: new Date(),
            extractTime: 0,
            transformTime: 0,
            loadTime: 0,
            totalTime: 0
          }
          setMessages(prev => [reconnectMsg, ...prev])
          setError(`Connection lost. Reconnecting... (Attempt ${reconnectAttemptsRef.current})`)
          
          // Reconnect after delay
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log(`🔄 Reconnecting... Attempt ${reconnectAttemptsRef.current}`)
            connectWebSocket() // Reconnect automatically
          }, delay)
        } else {
          // Max attempts reached
          setConnected(false)
          setError('Max reconnection attempts reached. Please check your connection and try again.')
        }
      }
    } catch (err) {
      setError(`Error creating WebSocket connection: ${err.message}. Make sure the URL is valid (starts with ws:// or wss://)`)
      setConnected(false)
      wsRef.current = null
      console.error('WebSocket connection error:', err)
    }
  }

  const disconnectWebSocket = () => {
    // Mark as manual disconnect to prevent auto-reconnection
    isManualDisconnectRef.current = true
    
    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    // Clear ping interval
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
    
    // Clear health check
    if (connectionHealthCheckRef.current) {
      clearInterval(connectionHealthCheckRef.current)
      connectionHealthCheckRef.current = null
    }
    
    // Reset reconnection attempts
    reconnectAttemptsRef.current = 0
    reconnectDelayRef.current = 1000

    // Close WebSocket connection
    if (wsRef.current) {
      try {
        wsRef.current.close(1000, 'User disconnected') // Normal closure
      } catch (err) {
        console.error('Error closing WebSocket:', err)
      }
      wsRef.current = null
    }
    
    setConnected(false)
    setError(null)
    const manualDisconnectMsg = {
      type: 'system', 
      message: 'Manually disconnected', 
      timestamp: new Date(),
      extractTime: 0,
      transformTime: 0,
      loadTime: 0,
      totalTime: 0
    }
    setMessages(prev => [manualDisconnectMsg, ...prev])
  }


  // Update messages per second display in real-time
  useEffect(() => {
    if (!connected) {
      setCurrentMessageRate(0)
      setUptime(0)
      return
    }

    const interval = setInterval(() => {
      const now = Date.now()
      if (now - lastSecondRef.current >= 1000) {
        messagesPerSecondRef.current = messageCountLastSecondRef.current
        setCurrentMessageRate(messageCountLastSecondRef.current)
        messageCountLastSecondRef.current = 0
        lastSecondRef.current = now
        
        // Update data to trigger re-render with new messagesPerSecond
        setData(prevData => {
          if (prevData) {
            return {
              ...prevData,
              messagesPerSecond: messagesPerSecondRef.current
            }
          }
          return prevData
        })
      }
      
      // Update uptime
      if (connectionTime) {
        setUptime(Math.floor((now - connectionTime) / 1000))
      }
    }, 100) // Check every 100ms

    return () => clearInterval(interval)
  }, [connected, setData, connectionTime])

  // Sync latencyData and throughputData to data object for Visualization section
  useEffect(() => {
    if (data && connected) {
      setData(prevData => {
        if (!prevData) return prevData
        return {
          ...prevData,
          latencyData: latencyData,
          throughputData: throughputData
        }
      })
    }
  }, [latencyData, throughputData, connected])

  useEffect(() => {
    return () => {
      disconnectWebSocket()
    }
  }, [])

  return (
    <div className="section-container">
      <div className="section-header">
        <div className="section-header-top">
          <div>
            <h2>⚡ WebSocket Section</h2>
            <p>Extract realtime data from WebSocket connections</p>
          </div>
          {connected && (
            <div className="websocket-view-sidebar" style={{ marginTop: 0, marginBottom: 0, borderBottom: 'none' }}>
              <div className="view-tabs">
                <button 
                  className={`view-tab ${activeView === 'stream' ? 'active' : ''}`}
                  onClick={() => setActiveView('stream')}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px', verticalAlign: 'middle' }}>
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                    <line x1="9" y1="9" x2="15" y2="9"></line>
                    <line x1="9" y1="15" x2="15" y2="15"></line>
                  </svg>
                  Live Stream
                </button>
                <button 
                  className={`view-tab ${activeView === 'dashboard' ? 'active' : ''}`}
                  onClick={() => setActiveView('dashboard')}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px', verticalAlign: 'middle' }}>
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                  </svg>
                  Dashboard
                </button>
                <button 
                  className={`view-tab ${activeView === 'list' ? 'active' : ''}`}
                  onClick={() => setActiveView('list')}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px', verticalAlign: 'middle' }}>
                    <line x1="8" y1="6" x2="21" y2="6"></line>
                    <line x1="8" y1="12" x2="21" y2="12"></line>
                    <line x1="8" y1="18" x2="21" y2="18"></line>
                    <line x1="3" y1="6" x2="3.01" y2="6"></line>
                    <line x1="3" y1="12" x2="3.01" y2="12"></line>
                    <line x1="3" y1="18" x2="3.01" y2="18"></line>
                  </svg>
                  List
                </button>
                <button 
                  className={`view-tab ${activeView === 'compare' ? 'active' : ''}`}
                  onClick={() => setActiveView('compare')}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px', verticalAlign: 'middle' }}>
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                  </svg>
                  Compare
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="section-content">
        <div className="websocket-input-area">
          <div className="websocket-input-grid">
            <div className="input-group">
              <label>Exchange</label>
              <select
                value={exchange}
                onChange={(e) => setExchange(e.target.value)}
                className="url-input"
                disabled={connected || !backendOnline}
                style={{ padding: '12px', background: '#f5f5f5', border: 'none', borderRadius: '6px' }}
              >
                <option value="custom">Custom WebSocket</option>
                <option value="okx">OKX</option>
                <option value="binance">Binance</option>
              </select>
            </div>

            {exchange === 'okx' && (
              <>
                <div className="input-group">
                  <label>OKX Channel</label>
                  <select
                    value={okxChannel}
                    onChange={(e) => setOkxChannel(e.target.value)}
                    className="url-input"
                    disabled={connected || !backendOnline}
                    style={{ padding: '12px', background: '#f5f5f5', border: 'none', borderRadius: '6px' }}
                  >
                    <option value="trades">Trades</option>
                    <option value="tickers">Tickers</option>
                    <option value="books5">Order Book (5 levels)</option>
                    <option value="books">Order Book (Full)</option>
                    <option value="candles">Candles</option>
                  </select>
                </div>
                <div className="input-group">
                  <label>OKX Instrument ID</label>
                  <select
                    value={okxInstId}
                    onChange={(e) => setOkxInstId(e.target.value)}
                    className="url-input"
                    disabled={connected || !backendOnline}
                    style={{ padding: '12px', background: '#f5f5f5', border: 'none', borderRadius: '6px' }}
                  >
                    {Object.entries(OKX_CONFIG.INSTRUMENTS).map(([key, value]) => (
                      <option key={key} value={value}>
                        {value === 'ALL' ? ' All Instruments' : value}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}

            {exchange === 'binance' && (
              <>
                <div className="input-group">
                  <label>Binance Symbol</label>
                  <select
                    value={binanceSymbol}
                    onChange={(e) => setBinanceSymbol(e.target.value)}
                    className="url-input"
                    disabled={connected || !backendOnline}
                    style={{ padding: '12px', background: '#f5f5f5', border: 'none', borderRadius: '6px' }}
                  >
                    {Object.entries(BINANCE_CONFIG.SYMBOLS).map(([key, value]) => (
                      <option key={key} value={value}>
                        {value === 'ALL' ? ' All Instruments' : value.toUpperCase()}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="input-group">
                  <label>Binance Stream Type</label>
                  <select
                    value={binanceStreamType}
                    onChange={(e) => setBinanceStreamType(e.target.value)}
                    className="url-input"
                    disabled={connected || !backendOnline}
                    style={{ padding: '12px', background: '#f5f5f5', border: 'none', borderRadius: '6px' }}
                  >
                    <option value="trade">Trade</option>
                    <option value="ticker">Ticker</option>
                    <option value="depth">Depth (Order Book)</option>
                  </select>
                </div>
              </>
            )}

            {exchange === 'custom' && (
              <>
                <div className="input-group">
                  <label>WebSocket URL</label>
                  <input
                    type="text"
                    value={wsUrl}
                    onChange={(e) => setWsUrl(e.target.value)}
                    placeholder="wss://ws.okx.com:8443/ws/v5/public"
                    className="url-input"
                    disabled={connected || !backendOnline}
                  />
                </div>
              </>
            )}
          </div>

          {exchange === 'custom' && (
            <div className="input-group">
              <label>Subscription Message (JSON - Optional)</label>
              <textarea
                value={subscriptionMessage}
                onChange={(e) => setSubscriptionMessage(e.target.value)}
                placeholder='{"op": "subscribe", "args": [{"channel": "trades", "instId": "BTC-USDT"}]}'
                className="json-textarea"
                rows={4}
                disabled={connected || !backendOnline}
              />
              <small style={{ color: '#666', fontSize: '0.7rem', marginTop: '5px', display: 'block' }}>
                Enter JSON subscription message to send after connection. Examples:<br/>
                OKX: {'{"op": "subscribe", "args": [{"channel": "trades", "instId": "BTC-USDT"}]}'}<br/>
                Binance: {'{"method": "SUBSCRIBE", "params": ["btcusdt@trade"], "id": 1}'}
              </small>
            </div>
          )}

          {(exchange === 'okx' || exchange === 'binance') && (
            <div className="input-group">
              <label>WebSocket URL (Auto-filled)</label>
              <input
                type="text"
                value={exchange === 'okx' ? OKX_CONFIG.WS_URL : `${BINANCE_CONFIG.WS_URL}${BINANCE_CONFIG.createStreamName(binanceSymbol, binanceStreamType)}`}
                className="url-input"
                disabled={true}
                style={{ background: '#e8e8e8', color: '#666' }}
              />
            </div>
          )}

          <div className="button-group">
            {!connected ? (
              <button 
                onClick={connectWebSocket} 
                disabled={(exchange === 'custom' && !wsUrl) || connected || !backendOnline}
                className="extract-button"
              >
                Live Stream
              </button>
            ) : (
              <button 
                onClick={disconnectWebSocket}
                className="stop-button"
              >
                Stop Stream
              </button>
            )}
          </div>

          {error && <div className="error-message">{error}</div>}

          {/* Dashboard View */}
          {activeView === 'dashboard' && connected && data && (
            <div className="dashboard-container">
              <RealtimeStream 
                websocketData={data}
                messages={messages}
                latencyData={latencyData}
                throughputData={throughputData}
                defaultTab="dashboard"
                exchange={exchange}
              />
            </div>
          )}

          {/* List View - Using RealtimeStream for real-time instrument display */}
          {activeView === 'list' && connected && data && (
            <div className="list-container">
              <RealtimeStream 
                websocketData={data}
                messages={messages}
                latencyData={latencyData}
                throughputData={throughputData}
                defaultTab="list"
                exchange={exchange}
              />
            </div>
          )}

          {/* Compare View - Real-time comparison */}
          {activeView === 'compare' && connected && data && (
            <div className="compare-container">
              <RealtimeStream 
                websocketData={data}
                messages={messages}
                latencyData={latencyData}
                throughputData={throughputData}
                defaultTab="compare"
                exchange={exchange}
              />
            </div>
          )}

          {/* Real-time Messages Display */}
          {activeView === 'stream' && messages.length > 0 && (
            <div className="websocket-messages-stream">
              <div className="stream-header-info">
                <div className="stream-stats-row">
                  {connected && (
                    <span className="live-indicator">
                      <span className="live-dot"></span>
                      LIVE
                    </span>
                  )}
                  <span className="stream-stat">
                    Messages: <strong>{messages.filter(m => m.type === 'data').length}</strong>
                  </span>
                  {dataFormat && (
                    <span className="stream-stat">
                      Format: <strong>{dataFormat}</strong>
                    </span>
                  )}
                  {isRealtime && exchange === 'custom' && (
                    <span className="stream-stat" style={{ color: '#16c784' }}>
                      <strong>🔄 Real-time Mode</strong>
                    </span>
                  )}
                  {currentMessageRate > 0 && (
                    <span className="stream-stat">
                      Rate: <strong>{currentMessageRate.toFixed(1)}/s</strong>
                    </span>
                  )}
                  {uptime > 0 && (
                    <span className="stream-stat">
                      Uptime: <strong>{uptime}s</strong>
                    </span>
                  )}
                </div>
              </div>
              <div className="messages-stream-container">
                {messages
                  .filter(msg => msg.type === 'data') // Only show data messages, not system messages
                  .map((msg, idx) => (
                    <div key={idx} className="stream-message-item data">
                      <div className="message-header-row">
                        <span className="message-number">#{msg.messageNumber || idx + 1}</span>
                        <span className="message-timestamp">
                          {msg.timestamp.toLocaleTimeString()}.{msg.timestamp.getMilliseconds().toString().padStart(3, '0')}
                        </span>
                        {msg.format && (
                          <span className="message-format">{msg.format}</span>
                        )}
                        {msg.extractTime !== undefined && (
                          <span className="message-timing">E:{msg.extractTime.toFixed(3)}s</span>
                        )}
                        {msg.transformTime !== undefined && (
                          <span className="message-timing">T:{msg.transformTime.toFixed(3)}s</span>
                        )}
                        {msg.loadTime !== undefined && (
                          <span className="message-timing">L:{msg.loadTime.toFixed(3)}s</span>
                        )}
                      </div>
                      <pre className="message-content-stream">
                        {JSON.stringify(msg.data, null, 2)}
                      </pre>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Live Charts Section */}
          {showCharts && connected && messages.filter(m => m.type === 'data').length > 0 && (
            <div className="websocket-charts-section">
              <h3>Real-time Performance Metrics - {exchange.toUpperCase()}</h3>
              <div className="charts-grid">
                {/* Latency Chart - Real-time latency per message */}
                <div className="chart-container">
                  <h4>Latency (ms) - Real-time Message Latency</h4>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={latencyData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="messageNumber" 
                        label={{ value: 'Message Number', position: 'insideBottom', offset: -5 }}
                      />
                      <YAxis 
                        label={{ value: 'Latency (ms)', angle: -90, position: 'insideLeft' }}
                      />
                      <Tooltip 
                        formatter={(value) => [`${value.toFixed(2)} ms`, 'Latency']}
                        labelFormatter={(label) => `Message #${label}`}
                      />
                      <Legend />
                      <Line 
                        type="monotone" 
                        dataKey="latency" 
                        stroke={exchange === 'okx' ? '#8884d8' : '#82ca9d'} 
                        name={`${exchange.toUpperCase()} Latency`}
                        dot={false}
                        strokeWidth={2}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Throughput Chart - Messages per second over time */}
                <div className="chart-container">
                  <h4>Throughput (msg/s) - Messages Per Second</h4>
                  <ResponsiveContainer width="100%" height={250}>
                    <AreaChart data={throughputData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="time" 
                        tickFormatter={(value) => {
                          const date = new Date(value)
                          return `${date.getMinutes()}:${date.getSeconds().toString().padStart(2, '0')}`
                        }}
                        label={{ value: 'Time', position: 'insideBottom', offset: -5 }}
                      />
                      <YAxis 
                        label={{ value: 'Messages/sec', angle: -90, position: 'insideLeft' }}
                      />
                      <Tooltip 
                        formatter={(value) => [`${value} msg/s`, 'Throughput']}
                        labelFormatter={(value) => {
                          const date = new Date(value)
                          return date.toLocaleTimeString()
                        }}
                      />
                      <Legend />
                      <Area 
                        type="monotone" 
                        dataKey="throughput" 
                        stroke={exchange === 'okx' ? '#8884d8' : '#82ca9d'}
                        fill={exchange === 'okx' ? '#8884d8' : '#82ca9d'}
                        fillOpacity={0.6}
                        name={`${exchange.toUpperCase()} Throughput`}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                {/* Scalability Chart - Cumulative metrics showing system performance */}
                <div className="chart-container">
                  <h4>Scalability - System Performance Over Time</h4>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={scalabilityData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="time" 
                        tickFormatter={(value) => {
                          const date = new Date(value)
                          return `${date.getMinutes()}:${date.getSeconds().toString().padStart(2, '0')}`
                        }}
                        label={{ value: 'Time', position: 'insideBottom', offset: -5 }}
                      />
                      <YAxis yAxisId="left" label={{ value: 'Total Messages', angle: -90, position: 'insideLeft' }} />
                      <YAxis yAxisId="right" orientation="right" label={{ value: 'Latency (ms) / Throughput', angle: 90, position: 'insideRight' }} />
                      <Tooltip 
                        formatter={(value, name) => {
                          if (name === 'Total Messages') return [value, 'Total Messages']
                          if (name === 'Avg Latency') return [`${value.toFixed(2)} ms`, 'Avg Latency']
                          return [`${value} msg/s`, 'Throughput']
                        }}
                        labelFormatter={(value) => {
                          const date = new Date(value)
                          return date.toLocaleTimeString()
                        }}
                      />
                      <Legend />
                      <Line 
                        yAxisId="left"
                        type="monotone" 
                        dataKey="totalMessages" 
                        stroke="#8884d8" 
                        name="Total Messages"
                        strokeWidth={2}
                      />
                      <Line 
                        yAxisId="right"
                        type="monotone" 
                        dataKey="avgLatency" 
                        stroke="#ff7300" 
                        name="Avg Latency (ms)"
                        strokeWidth={2}
                      />
                      <Line 
                        yAxisId="right"
                        type="monotone" 
                        dataKey="currentThroughput" 
                        stroke="#82ca9d" 
                        name="Throughput (msg/s)"
                        strokeWidth={2}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Performance Summary */}
                <div className="chart-container">
                  <h4>Performance Summary</h4>
                  <div className="performance-summary">
                    <div className="summary-item">
                      <span className="summary-label">Exchange:</span>
                      <span className="summary-value">{exchange.toUpperCase()}</span>
                    </div>
                    <div className="summary-item">
                      <span className="summary-label">Total Messages:</span>
                      <span className="summary-value">{messageCountRef.current}</span>
                    </div>
                    <div className="summary-item">
                      <span className="summary-label">Current Throughput:</span>
                      <span className="summary-value">{currentMessageRate.toFixed(1)} msg/s</span>
                    </div>
                    <div className="summary-item">
                      <span className="summary-label">Avg Latency:</span>
                      <span className="summary-value">
                        {latencyData.length > 0 
                          ? (latencyData.reduce((sum, d) => sum + d.latency, 0) / latencyData.length).toFixed(2)
                          : '0.00'
                        } ms
                      </span>
                    </div>
                    <div className="summary-item">
                      <span className="summary-label">Min Latency:</span>
                      <span className="summary-value">
                        {latencyData.length > 0 
                          ? Math.min(...latencyData.map(d => d.latency)).toFixed(2)
                          : '0.00'
                        } ms
                      </span>
                    </div>
                    <div className="summary-item">
                      <span className="summary-label">Max Latency:</span>
                      <span className="summary-value">
                        {latencyData.length > 0 
                          ? Math.max(...latencyData.map(d => d.latency)).toFixed(2)
                          : '0.00'
                        } ms
                      </span>
                    </div>
                    <div className="summary-item">
                      <span className="summary-label">Peak Throughput:</span>
                      <span className="summary-value">
                        {throughputData.length > 0 
                          ? Math.max(...throughputData.map(d => d.throughput))
                          : '0'
                        } msg/s
                      </span>
                    </div>
                    <div className="summary-item">
                      <span className="summary-label">Uptime:</span>
                      <span className="summary-value">{uptime}s</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default WebSocketSection

