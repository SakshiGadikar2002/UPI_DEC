import { useState, useEffect, useRef } from 'react'
import './Section.css'
import RealtimeStream from './RealtimeStream'
import { fetchDetailedMarketData } from '../utils/cryptoMarketData'

function VisualizationSection() {
  const [activeView, setActiveView] = useState('dashboard') // 'dashboard', 'list', or 'compare'
  const [marketData, setMarketData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [updateCount, setUpdateCount] = useState(0)
  const intervalRef = useRef(null)
  const messagesRef = useRef([])

  // Fetch global crypto market data continuously
  useEffect(() => {
    let isMounted = true
    const connectionStartTime = Date.now()
    let messageCount = 0
    
    const fetchData = async () => {
      try {
        if (!isMounted) return
        
        setIsLoading(false)
        setError(null)
        
        const result = await fetchDetailedMarketData()
        
        if (!isMounted) return
        
        messageCount++
        
        // Extract coins and global stats
        const coinsData = result.coins || []
        const globalStats = result.globalStats || null
        
        // Transform to format expected by RealtimeStream
        const now = Date.now()
        setMarketData(prevData => {
          const connectionTime = prevData?.connectionTime || connectionStartTime
          const firstMessageTime = prevData?.firstMessageTime || connectionStartTime
          
          const transformedData = {
            source: 'Global Crypto Market',
            url: 'https://api.coingecko.com/api/v3',
            mode: 'Realtime',
            data: coinsData,
            globalStats: globalStats, // Include global market stats
            totalRows: coinsData.length,
            duplicateCount: 0,
            totalMessages: messageCount,
            messagesPerSecond: 0.033, // Update every 30 seconds ≈ 0.033 msg/s
            transformed: coinsData.length,
            timestamp: new Date().toISOString(),
            messages: [], // Will be set below
            dataFormat: 'Global Market Data',
            connectionTime: connectionTime,
            firstMessageTime: firstMessageTime,
            currentMessageRate: 0.033,
            uptime: Math.floor((now - connectionTime) / 1000),
            timingData: [],
            isRealtime: true,
            latencyData: [],
            throughputData: [],
            exchange: 'global' // Use 'global' instead of 'okx', 'binance', or 'custom'
          }

          // Create synthetic messages for each update
          const syntheticMessage = {
            type: 'data',
            data: coinsData[0] || coinsData, // Use first item as sample
            timestamp: new Date(now),
            format: 'Global Market Data',
            messageNumber: messageCount,
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
      } catch (err) {
        if (!isMounted) return
        console.error('Error fetching market data:', err)
        // Provide user-friendly error messages
        let errorMessage = err.message
        if (err.message.includes('429') || err.message.includes('Rate limit') || err.message.includes('Too Many Requests')) {
          errorMessage = 'Rate limit exceeded. Data will refresh automatically. Please wait a few minutes.'
        } else if (err.message.includes('timeout') || err.message.includes('Timeout')) {
          errorMessage = 'Request timeout. Please check your connection and try again.'
        }
        setError(errorMessage)
        setIsLoading(false)
      }
    }

    // Fetch immediately
    fetchData()

    // Then fetch every 5 minutes (300000ms) to avoid rate limiting and reduce flickering
    intervalRef.current = setInterval(fetchData, 300000)

    return () => {
      isMounted = false
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, []) // Only run once on mount

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

