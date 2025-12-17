import { useState, useEffect, useRef, useCallback } from 'react'
import './Section.css'
import RealtimeStream from './RealtimeStream'
import { fetchDetailedMarketData } from '../utils/cryptoMarketData'

// Refresh interval: 20 seconds (20000ms) for real-time market data updates
const REFRESH_INTERVAL = 20000

function VisualizationSection() {
  const [activeView, setActiveView] = useState('dashboard') // 'dashboard', 'list', or 'compare'
  const [marketData, setMarketData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [updateCount, setUpdateCount] = useState(0)
  const intervalRef = useRef(null)
  const messagesRef = useRef([])
  const isFetchingRef = useRef(false) // Prevent concurrent fetches
  const connectionStartTimeRef = useRef(Date.now())
  const messageCountRef = useRef(0)
  const isFirstFetchRef = useRef(true) // Track if this is the first fetch

  // Optimized fetch function with debouncing to prevent concurrent requests
  const fetchData = useCallback(async () => {
    // Prevent concurrent fetches
    if (isFetchingRef.current) {
      console.log('Fetch already in progress, skipping...')
      return
    }

    try {
      isFetchingRef.current = true
      // Only show loading on first fetch
      if (isFirstFetchRef.current) {
        setIsLoading(true)
      }
      setError(null)
      
      const result = await fetchDetailedMarketData()
      
      messageCountRef.current++
      
      // Extract coins and global stats
      const coinsData = result.coins || []
      const globalStats = result.globalStats || null
      
      // Transform to format expected by RealtimeStream
      const now = Date.now()
      setMarketData(prevData => {
        // Preserve connection metadata across updates
        const connectionTime = prevData?.connectionTime || connectionStartTimeRef.current
        const firstMessageTime = prevData?.firstMessageTime || connectionStartTimeRef.current
        
        // Calculate accurate message rate (updates every 20 seconds = 0.05 msg/s)
        const messagesPerSecond = 1 / (REFRESH_INTERVAL / 1000)
        
        const transformedData = {
          source: 'Global Crypto Market',
          url: 'https://api.coingecko.com/api/v3',
          mode: 'Realtime',
          data: coinsData,
          globalStats: globalStats, // Include global market stats
          totalRows: coinsData.length,
          duplicateCount: 0,
          totalMessages: messageCountRef.current,
          messagesPerSecond: messagesPerSecond,
          transformed: coinsData.length,
          timestamp: new Date().toISOString(),
          messages: [], // Will be set below
          dataFormat: 'Global Market Data',
          connectionTime: connectionTime,
          firstMessageTime: firstMessageTime,
          currentMessageRate: messagesPerSecond,
          uptime: Math.floor((now - connectionTime) / 1000),
          timingData: [],
          isRealtime: true,
          latencyData: [],
          throughputData: [],
          exchange: 'global' // Use 'global' instead of 'okx', 'binance', or 'custom'
        }

        // Create synthetic messages for each update (keep last 100)
        const syntheticMessage = {
          type: 'data',
          data: coinsData[0] || coinsData, // Use first item as sample
          timestamp: new Date(now),
          format: 'Global Market Data',
          messageNumber: messageCountRef.current,
          extractTime: 0.5,
          transformTime: 0.1,
          loadTime: 0.05,
          totalTime: 0.65,
          exchange: 'global'
        }
        
        messagesRef.current = [syntheticMessage, ...messagesRef.current].slice(0, 100)
        transformedData.messages = messagesRef.current

        return transformedData
      })
      
      setUpdateCount(prev => prev + 1)
      setIsLoading(false)
      isFirstFetchRef.current = false // Mark that first fetch is complete
    } catch (err) {
      console.error('Error fetching market data:', err)
      // Provide user-friendly error messages
      let errorMessage = err.message
      if (err.message.includes('429') || err.message.includes('Rate limit') || err.message.includes('Too Many Requests')) {
        errorMessage = 'Rate limit exceeded. Data will refresh automatically. Please wait.'
      } else if (err.message.includes('timeout') || err.message.includes('Timeout')) {
        errorMessage = 'Request timeout. Please check your connection and try again.'
      }
      setError(errorMessage)
      setIsLoading(false)
    } finally {
      isFetchingRef.current = false
    }
  }, []) // No dependencies - uses refs for state that doesn't need to trigger re-renders

  // Fetch global crypto market data continuously with optimized 20-second interval
  useEffect(() => {
    let isMounted = true
    
    // Fetch immediately on mount
    fetchData()

    // Then fetch every 20 seconds for real-time updates
    intervalRef.current = setInterval(() => {
      if (isMounted) {
        fetchData()
      }
    }, REFRESH_INTERVAL)

    return () => {
      isMounted = false
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [fetchData]) // fetchData is stable via useCallback with no dependencies

  const connected = marketData !== null && !error

  return (
    <div className="section-container">
      <div className="section-header">
        <div className="section-header-top">
          <div>
            <h2>📊 Visualization</h2>
            <p>Global live cryptocurrency market data - Dashboard, List, and Compare views</p>
          </div>
          {connected && (
            <div className="websocket-view-sidebar" style={{ marginTop: 0, marginBottom: 0, borderBottom: 'none' }}>
              <div className="view-tabs">
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
        {isLoading ? (
          <div className="empty-state" style={{ padding: '40px', textAlign: 'center' }}>
            <p style={{ fontSize: '1.1em', color: '#666', marginBottom: '10px' }}>
              Loading global cryptocurrency market data...
            </p>
            <p style={{ fontSize: '0.9em', color: '#999' }}>
              Fetching live data from global markets
            </p>
          </div>
        ) : error ? (
          <div className="empty-state" style={{ padding: '40px', textAlign: 'center' }}>
            <p style={{ fontSize: '1.1em', color: '#d32f2f', marginBottom: '10px' }}>
              Error loading market data
            </p>
            <p style={{ fontSize: '0.9em', color: '#999' }}>
              {error}
            </p>
          </div>
        ) : !marketData ? (
          <div className="empty-state" style={{ padding: '40px', textAlign: 'center' }}>
            <p style={{ fontSize: '1.1em', color: '#666', marginBottom: '10px' }}>
              No market data available
            </p>
          </div>
        ) : (
          <>
            {/* Dashboard View */}
            {activeView === 'dashboard' && (
              <div className="dashboard-container">
                <RealtimeStream 
                  websocketData={marketData}
                  messages={marketData.messages || []}
                  latencyData={marketData.latencyData || []}
                  throughputData={marketData.throughputData || []}
                  defaultTab="dashboard"
                  exchange="global"
                  globalStats={marketData.globalStats}
                />
              </div>
            )}

            {/* List View */}
            {activeView === 'list' && (
              <div className="list-container">
                <RealtimeStream 
                  websocketData={marketData}
                  messages={marketData.messages || []}
                  latencyData={marketData.latencyData || []}
                  throughputData={marketData.throughputData || []}
                  defaultTab="list"
                  exchange="global"
                  globalStats={marketData.globalStats}
                />
              </div>
            )}

            {/* Compare View */}
            {activeView === 'compare' && (
              <div className="compare-container">
                <RealtimeStream 
                  websocketData={marketData}
                  messages={marketData.messages || []}
                  latencyData={marketData.latencyData || []}
                  throughputData={marketData.throughputData || []}
                  defaultTab="compare"
                  exchange="global"
                  globalStats={marketData.globalStats}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default VisualizationSection

