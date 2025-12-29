import { useEffect, useState } from 'react'
import './PipelineViewer.css'

function FailedApiCallsViewer({ apiId, onClose = null }) {
  const apiBase = import.meta.env.VITE_API_BASE || ''
  const [failedApiCalls, setFailedApiCalls] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchFailedApiCalls = async (apiIdToFetch) => {
    setLoading(true)
    setError('')
    try {
      let url
      if (apiIdToFetch) {
        // Fetch for specific API
        url = `${apiBase}/api/pipeline/${apiIdToFetch}/failed-calls?limit=100`
      } else {
        // Fetch all failed calls
        url = `${apiBase}/api/pipeline/failed-calls/all?limit=200`
      }
      const resp = await fetch(url)
      if (resp.ok) {
        const data = await resp.json()
        setFailedApiCalls(data.failed_calls || [])
      } else {
        setError(`Failed to fetch failed API calls: ${resp.status}`)
        setFailedApiCalls([])
      }
    } catch (err) {
      console.error('Error fetching failed API calls:', err)
      setError(`Error: ${err.message}`)
      setFailedApiCalls([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchFailedApiCalls(apiId)
    // Refresh every 5 seconds
    const interval = setInterval(() => {
      fetchFailedApiCalls(apiId)
    }, 5000)
    return () => clearInterval(interval)
  }, [apiId, apiBase])

  return (
    <div className="failed-api-calls-viewer">
      <div className="pipeline-failed-calls">
        <div className="sidebar-title" style={{ marginBottom: '16px' }}>
          {apiId ? 'Failed API Calls' : 'All Failed API Calls'}
          {failedApiCalls.length > 0 && (
            <span className="failed-count-badge">{failedApiCalls.length}</span>
          )}
        </div>
        {loading ? (
          <div className="history-empty">Loading failed calls...</div>
        ) : error ? (
          <div className="pipeline-error">{error}</div>
        ) : failedApiCalls.length === 0 ? (
          <div className="history-empty">No failed API calls</div>
        ) : (
          <div className="failed-calls-list scrollable-activity">
            {failedApiCalls.map((failedCall) => (
              <div key={failedCall.id} className="failed-call-item">
                <div className="failed-call-header">
                  <div className="failed-call-api-name">{failedCall.api_name || failedCall.api_id}</div>
                  <div className="failed-call-timestamp">
                    {failedCall.timestamp ? new Date(failedCall.timestamp).toLocaleString() : 'n/a'}
                  </div>
                </div>
                <div className="failed-call-details">
                  <div className="failed-call-url">
                    <span className="meta-label">URL:</span>
                    <span className="meta-value">{failedCall.url || 'N/A'}</span>
                  </div>
                  <div className="failed-call-error">
                    <span className="meta-label">Error:</span>
                    <span className="error-message">{failedCall.error_message || 'Unknown error'}</span>
                  </div>
                  <div className="failed-call-meta">
                    {failedCall.status_code && (
                      <span className="status-pill status-failure">
                        HTTP {failedCall.status_code}
                      </span>
                    )}
                    {failedCall.step_name && (
                      <span className="step-badge">Step: {failedCall.step_name}</span>
                    )}
                    {failedCall.response_time_ms && (
                      <span className="response-time">Time: {failedCall.response_time_ms}ms</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default FailedApiCallsViewer

