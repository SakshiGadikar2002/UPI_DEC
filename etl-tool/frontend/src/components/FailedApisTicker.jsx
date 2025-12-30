import { useEffect, useState } from 'react'
import './FailedApisTicker.css'

function FailedApisTicker() {
  const apiBase = import.meta.env.VITE_API_BASE || ''
  const [failedApiCalls, setFailedApiCalls] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchFailedApiCalls = async () => {
    try {
      setLoading(true)
      const baseUrl = apiBase || ''
      const url = baseUrl ? `${baseUrl}/api/pipeline/failed-calls/all?limit=50` : '/api/pipeline/failed-calls/all?limit=50'
      const resp = await fetch(url)
      if (resp.ok) {
        const data = await resp.json()
        setFailedApiCalls(data.failed_calls || [])
      }
    } catch (err) {
      console.error('Error fetching failed API calls:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchFailedApiCalls()
    // Refresh every 10 seconds
    const interval = setInterval(() => {
      fetchFailedApiCalls()
    }, 10000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading && failedApiCalls.length === 0) {
    return null
  }

  if (failedApiCalls.length === 0) {
    return null
  }

  // Format failed API calls for display
  const tickerItems = failedApiCalls.map((failedCall) => {
    const apiName = failedCall.api_name || failedCall.api_id || 'Unknown API'
    const timestamp = failedCall.timestamp 
      ? new Date(failedCall.timestamp).toLocaleTimeString() 
      : ''
    const errorMsg = failedCall.error_message || 'Unknown error'
    const statusCode = failedCall.status_code ? `HTTP ${failedCall.status_code}` : ''
    
    return {
      id: failedCall.id || `${Date.now()}-${Math.random()}`,
      text: `${apiName} • ${errorMsg}${statusCode ? ` • ${statusCode}` : ''}${timestamp ? ` • ${timestamp}` : ''}`
    }
  })

  // Duplicate items for seamless loop
  const duplicatedItems = [...tickerItems, ...tickerItems]

  return (
    <div className="failed-apis-ticker-container">
      <div className="failed-apis-ticker-label">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="7" cy="7" r="5"/>
          <path d="M7 4v3M7 9h.01"/>
        </svg>
        <span>Failed APIs</span>
        <span className="failed-apis-count-badge">{failedApiCalls.length}</span>
      </div>
      <div className="failed-apis-ticker-wrapper">
        <div className="failed-apis-ticker-content">
          {duplicatedItems.map((item, index) => (
            <div key={`${item.id}-${index}`} className="failed-apis-ticker-item">
              <span className="ticker-separator">•</span>
              <span className="ticker-text">{item.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default FailedApisTicker

