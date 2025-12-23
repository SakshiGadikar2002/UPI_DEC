import { useState, useEffect } from 'react'
import './Section.css'
import './APIGatewaySection.css'

function APIGatewaySection() {
  const [telemetry, setTelemetry] = useState(null)
  const [connectors, setConnectors] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [timeRange, setTimeRange] = useState(24)
  const [selectedConnector, setSelectedConnector] = useState(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshInterval, setRefreshInterval] = useState(null)

  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

  const fetchTelemetry = async () => {
    try {
      setError(null)
      const url = selectedConnector 
        ? `${apiBase}/api/gateway/telemetry?hours=${timeRange}&connector_id=${selectedConnector}`
        : `${apiBase}/api/gateway/telemetry?hours=${timeRange}`
      
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(`Failed to fetch telemetry: ${response.statusText}`)
      }
      const data = await response.json()
      setTelemetry(data)
    } catch (err) {
      console.error('Error fetching telemetry:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fetchConnectors = async () => {
    try {
      const response = await fetch(`${apiBase}/api/gateway/connectors`)
      if (!response.ok) {
        throw new Error(`Failed to fetch connectors: ${response.statusText}`)
      }
      const data = await response.json()
      setConnectors(data)
    } catch (err) {
      console.error('Error fetching connectors:', err)
    }
  }

  useEffect(() => {
    fetchConnectors()
  }, [])

  useEffect(() => {
    fetchTelemetry()

    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchTelemetry()
      }, 30000) // Refresh every 30 seconds
      setRefreshInterval(interval)
      return () => clearInterval(interval)
    } else if (refreshInterval) {
      clearInterval(refreshInterval)
      setRefreshInterval(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRange, selectedConnector, autoRefresh])

  const formatNumber = (num) => {
    if (num === null || num === undefined) return 'N/A'
    if (typeof num === 'number') {
      return num.toLocaleString('en-US', { maximumFractionDigits: 2 })
    }
    return num
  }

  const formatLatency = (ms) => {
    if (ms === null || ms === undefined) return 'N/A'
    if (ms < 1000) return `${Math.round(ms)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const getStatusColor = (statusCode) => {
    if (!statusCode) return '#999'
    if (statusCode >= 200 && statusCode < 300) return '#22c55e'
    if (statusCode >= 300 && statusCode < 400) return '#3b82f6'
    if (statusCode >= 400 && statusCode < 500) return '#f59e0b'
    if (statusCode >= 500) return '#ef4444'
    return '#999'
  }

  const getErrorRateColor = (rate) => {
    if (rate === null || rate === undefined || rate === 0) return '#22c55e'
    if (rate < 1) return '#22c55e'
    if (rate < 5) return '#f59e0b'
    return '#ef4444'
  }

  const RefreshIcon = () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="23 4 23 10 17 10"></polyline>
      <polyline points="1 20 1 14 7 14"></polyline>
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
    </svg>
  )

  const PauseIcon = () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="6" y="4" width="4" height="16"></rect>
      <rect x="14" y="4" width="4" height="16"></rect>
    </svg>
  )

  const GatewayIcon = () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
      <line x1="3" y1="9" x2="21" y2="9"></line>
      <line x1="9" y1="21" x2="9" y2="9"></line>
      <circle cx="12" cy="6" r="1"></circle>
      <circle cx="6" cy="12" r="1"></circle>
      <circle cx="18" cy="12" r="1"></circle>
      <circle cx="12" cy="18" r="1"></circle>
    </svg>
  )

  const WarningIcon = () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
      <line x1="12" y1="9" x2="12" y2="13"></line>
      <line x1="12" y1="17" x2="12.01" y2="17"></line>
    </svg>
  )

  if (loading && !telemetry) {
    return (
      <div className="api-gateway-section">
        <div className="section-header">
          <div className="section-title">
            <GatewayIcon />
            <h2>API Gateway</h2>
          </div>
          <p>Loading telemetry data...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="api-gateway-section">
      <div className="section-header">
        <div className="section-header-top">
          <div className="section-title">
            <GatewayIcon />
            <div>
              <h2>API Gateway</h2>
              <p>API observability dashboard - Monitor health, performance, and usage metrics</p>
            </div>
          </div>
          <div className="gateway-controls">
            <select 
              value={timeRange} 
              onChange={(e) => setTimeRange(Number(e.target.value))}
              className="time-range-select"
            >
              <option value={1}>Last 1 hour</option>
              <option value={6}>Last 6 hours</option>
              <option value={24}>Last 24 hours</option>
              <option value={48}>Last 48 hours</option>
              <option value={168}>Last 7 days</option>
            </select>
            <select 
              value={selectedConnector || ''} 
              onChange={(e) => setSelectedConnector(e.target.value || null)}
              className="connector-filter-select"
            >
              <option value="">All APIs</option>
              {connectors.map(conn => (
                <option key={conn.connector_id} value={conn.connector_id}>
                  {conn.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`refresh-toggle ${autoRefresh ? 'active' : ''}`}
              title={autoRefresh ? 'Auto-refresh enabled (30s)' : 'Auto-refresh disabled'}
            >
              {autoRefresh ? <RefreshIcon /> : <PauseIcon />}
              <span>{autoRefresh ? 'Auto' : 'Paused'}</span>
            </button>
            <button
              onClick={fetchTelemetry}
              className="refresh-button"
              title="Refresh now"
            >
              <RefreshIcon />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <WarningIcon />
          <span>{error}</span>
          <button onClick={fetchTelemetry}>Retry</button>
        </div>
      )}

      {telemetry && (
        <div className="gateway-dashboard">
          {/* Overall Metrics - Clean inline display */}
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Total Requests</div>
              <div className="metric-value">{formatNumber(telemetry.overall.total_requests)}</div>
              <div className="metric-subtitle">Last {timeRange}h</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Error Rate</div>
              <div 
                className="metric-value" 
                style={{ color: getErrorRateColor(telemetry.overall.error_rate) }}
              >
                {telemetry.overall.error_rate !== null && telemetry.overall.error_rate !== undefined 
                  ? `${formatNumber(telemetry.overall.error_rate)}%` 
                  : '0%'}
              </div>
              <div className="metric-subtitle">
                4xx: {telemetry.overall.error_4xx || 0} | 5xx: {telemetry.overall.error_5xx || 0}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Avg Latency</div>
              <div className="metric-value">{formatLatency(telemetry.overall.avg_latency_ms)}</div>
              <div className="metric-subtitle">
                P95: {formatLatency(telemetry.overall.p95_latency_ms)} | P99: {formatLatency(telemetry.overall.p99_latency_ms)}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Pipeline Success</div>
              <div 
                className="metric-value"
                style={{ color: telemetry.pipeline_stats.success_rate >= 95 ? '#22c55e' : '#f59e0b' }}
              >
                {formatNumber(telemetry.pipeline_stats.success_rate)}%
              </div>
              <div className="metric-subtitle">
                {telemetry.pipeline_stats.successful_runs} / {telemetry.pipeline_stats.total_runs} runs
              </div>
            </div>
          </div>

          {/* Per-Connector Table - Full Width */}
          {telemetry.per_connector && telemetry.per_connector.length > 0 && (
            <div className="table-container">
              <h3>API Performance by Connector</h3>
              <table className="connector-table">
                <thead>
                  <tr>
                    <th>Connector</th>
                    <th>Requests</th>
                    <th>Error Rate</th>
                    <th>4xx</th>
                    <th>5xx</th>
                    <th>Avg Latency</th>
                    <th>P95 Latency</th>
                    <th>Last Request</th>
                  </tr>
                </thead>
                <tbody>
                  {telemetry.per_connector.map((conn, idx) => (
                    <tr key={idx}>
                      <td className="connector-name">{conn.connector_id}</td>
                      <td>{formatNumber(conn.request_count)}</td>
                      <td>
                        <span style={{ color: getErrorRateColor(conn.error_rate) }}>
                          {conn.error_rate !== null && conn.error_rate !== undefined 
                            ? `${formatNumber(conn.error_rate)}%` 
                            : '0%'}
                        </span>
                      </td>
                      <td>{conn.error_4xx || 0}</td>
                      <td>{conn.error_5xx || 0}</td>
                      <td>{formatLatency(conn.avg_latency_ms)}</td>
                      <td>{formatLatency(conn.p95_latency_ms)}</td>
                      <td>
                        {conn.last_request_at 
                          ? new Date(conn.last_request_at).toLocaleString('en-US', { 
                              month: 'short', 
                              day: 'numeric', 
                              hour: '2-digit', 
                              minute: '2-digit' 
                            })
                          : 'N/A'
                        }
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Side-by-Side Section: Status Codes and Bottom Stats */}
          <div className="main-content-grid">
            {/* Status Code Distribution */}
            {telemetry.status_codes && telemetry.status_codes.length > 0 && (
              <div className="status-codes-container">
                <h3>Status Code Distribution</h3>
                <div className="status-codes-grid">
                  {telemetry.status_codes.map((item, idx) => (
                    <div key={idx} className="status-code-item">
                      <div 
                        className="status-code-badge"
                        style={{ backgroundColor: getStatusColor(item.status_code) }}
                      >
                        {item.status_code}
                      </div>
                      <div className="status-code-count">{formatNumber(item.count)}</div>
                      <div className="status-code-percent">
                        {formatNumber((item.count / telemetry.overall.total_requests) * 100)}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Right Side: Failures and Pipeline Stats */}
            <div className="right-side-container">
              {/* Recent Failures */}
              {telemetry.recent_failures && telemetry.recent_failures.length > 0 && (
                <div className="failures-container">
                  <h3>Recent Failures ({telemetry.recent_failures.length})</h3>
                  <table className="failures-table">
                    <thead>
                      <tr>
                        <th>Connector</th>
                        <th>Timestamp</th>
                        <th>Status Code</th>
                        <th>Response Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {telemetry.recent_failures.slice(0, 20).map((failure, idx) => (
                        <tr key={idx}>
                          <td>{failure.connector_id}</td>
                          <td>
                            {new Date(failure.timestamp).toLocaleString('en-US', { 
                              month: 'short', 
                              day: 'numeric', 
                              hour: '2-digit', 
                              minute: '2-digit',
                              second: '2-digit'
                            })}
                          </td>
                          <td>
                            <span 
                              className="status-code-badge-small"
                              style={{ backgroundColor: getStatusColor(failure.status_code) }}
                            >
                              {failure.status_code}
                            </span>
                          </td>
                          <td>{formatLatency(failure.response_time_ms)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Pipeline Statistics */}
              <div className="pipeline-stats-container">
                <h3>Pipeline Run Statistics</h3>
                <div className="pipeline-stats-grid">
                  <div className="pipeline-stat-item">
                    <div className="pipeline-stat-label">Total Runs</div>
                    <div className="pipeline-stat-value">{formatNumber(telemetry.pipeline_stats.total_runs)}</div>
                  </div>
                  <div className="pipeline-stat-item success">
                    <div className="pipeline-stat-label">Successful</div>
                    <div className="pipeline-stat-value">{formatNumber(telemetry.pipeline_stats.successful_runs)}</div>
                  </div>
                  <div className="pipeline-stat-item failure">
                    <div className="pipeline-stat-label">Failed</div>
                    <div className="pipeline-stat-value">{formatNumber(telemetry.pipeline_stats.failed_runs)}</div>
                  </div>
                  <div className="pipeline-stat-item running">
                    <div className="pipeline-stat-label">Running</div>
                    <div className="pipeline-stat-value">{formatNumber(telemetry.pipeline_stats.running_runs)}</div>
                  </div>
                  <div className="pipeline-stat-item">
                    <div className="pipeline-stat-label">Avg Duration</div>
                    <div className="pipeline-stat-value">{formatLatency(telemetry.pipeline_stats.avg_run_duration_ms)}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default APIGatewaySection

