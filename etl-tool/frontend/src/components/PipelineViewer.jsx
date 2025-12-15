import { useEffect, useMemo, useState } from 'react'
import ReactFlow, { Background, Controls, MiniMap } from 'react-flow-renderer'
import './PipelineViewer.css'

const statusColors = {
  running: '#2F80ED',
  success: '#27AE60',
  failure: '#EB5757',
  pending: '#BDBDBD',
}

const fallbackSteps = ['extract', 'transform', 'load']

const defaultNodeStyle = {
  color: '#111827',
  borderWidth: 2,
  borderStyle: 'solid',
  borderRadius: 8,
  padding: '12px 14px',
  fontSize: '13px',
  width: 160,
}

const buildLabel = (title, status, tooltip, recordCount = null) => (
  <div className="pipeline-node-label" title={tooltip || ''}>
    <div className="pipeline-node-title">{title}</div>
    <div className={`pipeline-node-status status-${status || 'pending'}`}>
      {recordCount !== null && recordCount !== undefined ? `${recordCount} records` : (status || 'pending')}
    </div>
  </div>
)

function PipelineViewer({ visible = true, apiId = null, onClose = null }) {
  const apiBase = import.meta.env.VITE_API_BASE || ''
  const [selectedApi, setSelectedApi] = useState(apiId || '')
  const [pipelineData, setPipelineData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [options, setOptions] = useState([])
  const [showFitViewModal, setShowFitViewModal] = useState(false)

  // When apiId is provided (from running connector), use it directly - no dropdown needed
  useEffect(() => {
    if (apiId) {
      setSelectedApi(apiId)
    }
  }, [apiId])

  // Load pipeline list from backend only if no apiId is forced (for scheduled APIs)
  useEffect(() => {
    if (apiId) return // Skip loading options if apiId is forced from running connector
    const loadOptions = async () => {
      try {
        const resp = await fetch(`${apiBase}/api/pipeline`)
        if (!resp.ok) throw new Error(`Failed to load pipelines (${resp.status})`)
        const data = await resp.json()
        const normalized = data.map((item) => ({
          id: item.api_id,
          name: item.api_name || item.api_id,
          url: item.source_url,
        }))
        setOptions(normalized)
        if (normalized.length > 0 && !selectedApi) {
          setSelectedApi(normalized[0].id)
        }
      } catch (err) {
        console.error('Failed to load pipeline list', err)
      }
    }
    if (visible) {
      loadOptions()
    }
  }, [apiBase, visible, apiId])

  const fetchPipeline = async (apiIdToFetch) => {
    if (!apiIdToFetch) return
    setLoading(true)
    setError('')
    try {
      let resp = await fetch(`${apiBase}/api/etl/pipeline/${apiIdToFetch}`)
      if (!resp.ok) {
        resp = await fetch(`${apiBase}/api/pipeline/${apiIdToFetch}`)
      }
      if (!resp.ok) {
        throw new Error(`Pipeline endpoint returned ${resp.status}`)
      }
      const data = await resp.json()
      console.log('Pipeline data received:', data)
      console.log('Current run steps:', data?.current_run?.steps)
      console.log('History steps:', data?.history?.[0]?.steps)
      setPipelineData(data)
    } catch (err) {
      console.error('Failed to fetch pipeline', err)
      setError(err.message || 'Unable to load pipeline')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!visible) return undefined
    if (!selectedApi) {
      setPipelineData(null)
      return undefined
    }
    fetchPipeline(selectedApi)
    const interval = setInterval(() => fetchPipeline(selectedApi), 1800000) // Update every 30 minutes to reduce flickering
    return () => clearInterval(interval)
  }, [selectedApi, visible])

  const stepStatuses = useMemo(() => {
    const statuses = {}
    // Get steps from current run, or fallback to latest history run if no current run
    const steps = pipelineData?.current_run?.steps || 
                  pipelineData?.history?.[0]?.steps || 
                  []
    console.log('StepStatuses - Processing steps:', steps)
    steps.forEach((step) => {
      // Handle both step_name and stepName (camelCase) field names
      const stepName = step?.step_name || step?.stepName
      if (step && stepName) {
        statuses[stepName] = step.status || 'pending'
        console.log(`StepStatuses - Added: ${stepName} = ${statuses[stepName]}`)
      } else {
        console.warn('StepStatuses - Skipping invalid step:', step)
      }
    })
    console.log('StepStatuses - Final statuses:', statuses)
    return statuses
  }, [pipelineData])

  const stepRecordCounts = useMemo(() => {
    const counts = {}
    const dataStats = pipelineData?.data_stats || {}
    // Get steps from current run, or fallback to latest history run if no current run
    const steps = pipelineData?.current_run?.steps || 
                  pipelineData?.history?.[0]?.steps || 
                  []
    
    steps.forEach((step) => {
      const stepName = step?.step_name || step?.stepName
      if (step && stepName) {
        let recordCount = null
        
        // Try to extract count from step details
        if (step.details) {
          try {
            const details = typeof step.details === 'string' ? JSON.parse(step.details) : step.details
            recordCount = details.records || details.items || details.count || null
          } catch (e) {
            // Keep null if parsing fails
          }
        }
        
        // Fallback to data_stats for specific steps
        if (recordCount === null || recordCount === undefined) {
          if (stepName === 'extract' && dataStats.total_records > 0) {
            recordCount = dataStats.total_records
          } else if (stepName === 'clean' && dataStats.total_records > 0) {
            recordCount = dataStats.total_records
          } else if (stepName === 'transform' && dataStats.total_items > 0) {
            recordCount = dataStats.total_items
          } else if (stepName === 'load' && dataStats.total_records > 0) {
            recordCount = dataStats.total_records
          }
        }
        
        counts[stepName] = recordCount
      }
    })
    
    return counts
  }, [pipelineData])

  const stepSequence = useMemo(() => {
    // Get steps from current run, or fallback to latest history run if no current run
    const steps = pipelineData?.current_run?.steps || 
                  pipelineData?.history?.[0]?.steps || 
                  []
    
    console.log('StepSequence - Raw steps from pipelineData:', steps)
    console.log('StepSequence - Current run:', pipelineData?.current_run)
    console.log('StepSequence - History[0]:', pipelineData?.history?.[0])
    
    if (steps && Array.isArray(steps) && steps.length > 0) {
      // Sort by step_order if available, otherwise maintain order
      const sortedSteps = [...steps].sort((a, b) => {
        const orderA = a?.step_order ?? a?.stepOrder ?? 999
        const orderB = b?.step_order ?? b?.stepOrder ?? 999
        return orderA - orderB
      })
      // Handle both step_name and stepName (camelCase) field names
      const stepNames = sortedSteps
        .map((s) => s?.step_name || s?.stepName)
        .filter(Boolean)
        .filter((name) => name && name.trim().length > 0)
      
      console.log('StepSequence - Extracted step names:', stepNames)
      if (stepNames.length > 0) {
        return stepNames
      }
    }
    console.log('StepSequence - No valid steps found, using fallback:', fallbackSteps)
    return fallbackSteps
  }, [pipelineData])

  const nodes = useMemo(() => {
    const flowNodes = []
    const positionList = (count) => Array.from({ length: count }, (_, idx) => ({ x: idx * 220, y: 120 }))
    const positions = positionList(stepSequence.length + 2)

    const destinationStatus = stepStatuses[stepSequence[stepSequence.length - 1]] || 'pending'

    console.log('Building nodes - stepSequence:', stepSequence)
    console.log('Building nodes - stepStatuses:', stepStatuses)

    flowNodes.push({
      id: 'source',
      data: { label: buildLabel('Source', 'success', pipelineData?.api?.source_url) },
      position: positions[0],
      style: { ...defaultNodeStyle, borderColor: statusColors.success, background: '#E0F2FE' },
    })

    stepSequence.forEach((stepName, idx) => {
      if (!stepName) {
        console.warn(`Skipping empty stepName at index ${idx}`)
        return // Skip if stepName is empty
      }
      const status = stepStatuses[stepName] || 'pending'
      const recordCount = stepRecordCounts[stepName]
      const displayName = stepName ? stepName.toUpperCase() : 'UNKNOWN'
      const labelElement = buildLabel(displayName, status, pipelineData?.api?.api_name, recordCount)
      console.log(`Creating node for step: ${stepName} with status: ${status}, recordCount: ${recordCount}, displayName: ${displayName}`, labelElement)
      
      flowNodes.push({
        id: stepName || `step-${idx}`,
        data: { label: labelElement },
        position: positions[idx + 1],
        style: {
          ...defaultNodeStyle,
          borderColor: statusColors[status] || statusColors.pending,
          background: `${statusColors[status] || statusColors.pending}20`,
        },
      })
    })

    flowNodes.push({
      id: 'destination',
      data: { label: buildLabel('Destination', destinationStatus, pipelineData?.api?.destination) },
      position: positions[positions.length - 1],
      style: {
        ...defaultNodeStyle,
        borderColor: statusColors[destinationStatus] || statusColors.pending,
        background: '#ECFDF3',
      },
    })

    console.log('Final nodes array:', flowNodes)
    return flowNodes
  }, [pipelineData, stepStatuses, stepSequence, stepRecordCounts])

  const edges = useMemo(() => {
    const flowEdges = []
    if (stepSequence.length > 0) {
      flowEdges.push({ id: 'e-source-first', source: 'source', target: stepSequence[0], animated: true })
      stepSequence.forEach((step, idx) => {
        const nextStep = stepSequence[idx + 1]
        if (nextStep) {
          flowEdges.push({ id: `e-${step}-${nextStep}`, source: step, target: nextStep, animated: true })
        }
      })
      flowEdges.push({
        id: 'e-last-destination',
        source: stepSequence[stepSequence.length - 1],
        target: 'destination',
        animated: true,
      })
    }
    return flowEdges
  }, [stepSequence])

  const active = pipelineData?.active && pipelineData?.current_run
  const selectedMeta = options.find((a) => a.id === selectedApi)
  const dataStats = pipelineData?.data_stats || {}

  if (!visible) return null

  return (
    <div className="pipeline-viewer">
      <div className="pipeline-header">
        <div>
          <p className="pipeline-title">API Pipeline Visualization</p>
          <p className="pipeline-subtitle">
            {apiId
              ? `Showing pipeline for the currently running API: ${apiId}`
              : 'Select an API to view its pipeline visualization.'}
          </p>
        </div>
        <div className="pipeline-actions">
          {onClose && (
            <button className="pipeline-refresh secondary" onClick={onClose}>
              Close
            </button>
          )}
          {!onClose && (
            <>
              <select
                value={selectedApi}
                onChange={(e) => setSelectedApi(e.target.value)}
                className="pipeline-select"
                disabled={!!apiId || options.length === 0}
              >
                {options.length === 0 && <option value="">No pipelines available</option>}
                {options.length > 0 && <option value="">Select an API</option>}
                {options.map((api) => (
                  <option key={api.id} value={api.id}>
                    {api.name}
                  </option>
                ))}
              </select>
              <button
                className="pipeline-refresh"
                onClick={() => fetchPipeline(selectedApi)}
                disabled={!selectedApi}
              >
                Refresh
              </button>
            </>
          )}
        </div>
      </div>

      {!selectedApi ? (
        <div className="pipeline-empty">Select an API to view its pipeline.</div>
      ) : loading ? (
        <div className="pipeline-empty">Loading pipeline...</div>
      ) : error ? (
        <div className="pipeline-error">{error}</div>
      ) : !pipelineData?.current_run ? (
        <div className="pipeline-empty">
          {options.length === 0
            ? 'No pipelines found in database. Start a scheduled run to create pipeline records.'
            : 'No recent pipeline runs for this API. Start or rerun it to view progress.'}
        </div>
      ) : (
        <div className="pipeline-body">
          <div className="pipeline-flow">
            <div className="pipeline-meta">
              <div>
                <div className="meta-label">API</div>
                <div className="meta-value">{pipelineData?.api?.api_name || selectedMeta?.name}</div>
                <div className="meta-hint">{pipelineData?.api?.source_url || selectedMeta?.url}</div>
              </div>
              <div>
                <div className="meta-label">Status</div>
                <div className={`status-pill status-${pipelineData?.current_run?.status || 'pending'}`}>
                  {pipelineData?.current_run?.status || 'pending'}
                </div>
              </div>
              <div>
                <div className="meta-label">Schedule</div>
                <div className="meta-value">
                  {pipelineData?.api?.schedule?.interval_seconds
                    ? `Every ${(pipelineData.api.schedule.interval_seconds / 60).toFixed(0)} min`
                    : '—'}
                </div>
                <div className="meta-hint">
                  Next run: {pipelineData?.api?.schedule?.next_run || 'n/a'}
                </div>
              </div>
              <div>
                <div className="meta-label">Data</div>
                <div className="meta-value">{dataStats.total_records ?? 0} rows</div>
                <div className="meta-hint">
                  Last data: {dataStats.last_data_at ? new Date(dataStats.last_data_at).toLocaleString() : 'n/a'}
                </div>
              </div>
            </div>
            <div className="pipeline-flowchart">
              <div style={{ position: 'relative', width: '100%', height: '100%' }}>
                <button
                  className="pipeline-fitview-button"
                  onClick={() => setShowFitViewModal(true)}
                  title="Open full view in popup"
                >
                  POP UP VIEW
                </button>
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  fitView
                  nodesDraggable={false}
                  nodesConnectable={false}
                  elementsSelectable={false}
                >
                  <MiniMap pannable={false} zoomable={false} />
                  <Controls />
                  <Background gap={20} color="#f0f4ff" />
                </ReactFlow>
              </div>
            </div>
            
            {/* Fit View Modal Popup */}
            {showFitViewModal && (
              <div className="pipeline-fitview-modal-overlay" onClick={() => setShowFitViewModal(false)}>
                <div className="pipeline-fitview-modal-content" onClick={(e) => e.stopPropagation()}>
                  <div className="pipeline-fitview-modal-header">
                    <h3>Pipeline Visualization - Full View</h3>
                    <button 
                      className="pipeline-fitview-modal-close"
                      onClick={() => setShowFitViewModal(false)}
                      aria-label="Close"
                    >
                      ×
                    </button>
                  </div>
                  <div className="pipeline-fitview-modal-body">
                    <div style={{ width: '100%', height: '100%' }}>
                      <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        fitView
                        nodesDraggable={false}
                        nodesConnectable={false}
                        elementsSelectable={false}
                      >
                        <MiniMap pannable={false} zoomable={false} />
                        <Controls />
                        <Background gap={20} color="#f0f4ff" />
                      </ReactFlow>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="pipeline-sidebar">
            <div className="sidebar-section">
              <div className="sidebar-title">Run history</div>
              <div className="history-list scrollable-history">
                {pipelineData?.history?.length === 0 && <div className="history-empty">No history yet</div>}
                {pipelineData?.history?.slice(0, 3).map((run) => (
                  <div key={run.run_id} className="history-item">
                    <div className="history-row">
                      <span className={`status-pill status-${run.status}`}>{run.status}</span>
                      <span className="history-time">
                        {run.started_at ? new Date(run.started_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '-'}
                      </span>
                    </div>
                    <div className="history-hint">
                      {run.duration_seconds ? `${run.duration_seconds.toFixed(1)}s` : 'in progress'}
                      {run.error_message ? ` • ${run.error_message}` : ''}
                    </div>
                  </div>
                ))}
                {pipelineData?.history?.length > 3 && (
                  <div className="history-scrollable">
                    {pipelineData.history.slice(3).map((run) => (
                      <div key={run.run_id} className="history-item">
                        <div className="history-row">
                          <span className={`status-pill status-${run.status}`}>{run.status}</span>
                          <span className="history-time">
                            {run.started_at ? new Date(run.started_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '-'}
                          </span>
                        </div>
                        <div className="history-hint">
                          {run.duration_seconds ? `${run.duration_seconds.toFixed(1)}s` : 'in progress'}
                          {run.error_message ? ` • ${run.error_message}` : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div className="sidebar-section">
              <div className="sidebar-title">Errors</div>
              {pipelineData?.current_run?.error_message ? (
                <div className="error-card">{pipelineData.current_run.error_message}</div>
              ) : (
                <div className="history-empty">No errors</div>
              )}
            </div>
          </div>

          <div className="pipeline-steps-table">
            <div className="pipeline-steps-head">Step timeline</div>
            <div className="pipeline-steps-list">
              {stepSequence.map((stepName) => {
                // Try to find step info from current run first, then latest history run
                const stepInfo =
                  pipelineData?.current_run?.steps?.find((s) => s?.step_name === stepName) ||
                  pipelineData?.history?.[0]?.steps?.find((s) => s?.step_name === stepName) ||
                  null
                const started = stepInfo?.started_at ? new Date(stepInfo.started_at).toLocaleTimeString() : '—'
                const finished = stepInfo?.completed_at
                  ? new Date(stepInfo.completed_at).toLocaleTimeString()
                  : '—'
                const details =
                  typeof stepInfo?.details === 'string'
                    ? stepInfo.details
                    : stepInfo?.details
                    ? JSON.stringify(stepInfo.details)
                    : ''
                
                // Extract count from details or data_stats
                let countDisplay = '—'
                // Always try to show count, regardless of status
                if (stepName === 'extract' && dataStats.total_records > 0) {
                  countDisplay = `${dataStats.total_records}`
                } else if (stepName === 'clean' && dataStats.total_records > 0) {
                  countDisplay = `${dataStats.total_records}`
                } else if (stepName === 'transform' && dataStats.total_items > 0) {
                  countDisplay = `${dataStats.total_items}`
                } else if (stepName === 'load' && dataStats.total_records > 0) {
                  countDisplay = `${dataStats.total_records}`
                } else if (details) {
                  try {
                    const parsed = typeof details === 'string' ? JSON.parse(details) : details
                    if (parsed.records) countDisplay = `${parsed.records}`
                    else if (parsed.items) countDisplay = `${parsed.items}`
                    else if (parsed.count) countDisplay = `${parsed.count}`
                  } catch (e) {
                    // Keep default
                  }
                }
                
                return (
                  <div className="pipeline-step-row" key={stepName}>
                    <div className="pipeline-step-name">{stepName.toUpperCase()}</div>
                    <div className="pipeline-step-status">
                      {countDisplay !== '—' ? (
                        <span className="pipeline-step-count">{countDisplay}</span>
                      ) : (
                        <span className="pipeline-step-empty">—</span>
                      )}
                    </div>
                    <div className="pipeline-step-details">
                      {stepInfo?.error_message || details || '—'}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {pipelineData?.activity_log?.length > 0 && (
            <div className="pipeline-activity-log">
              <div className="sidebar-title">Recent loads</div>
              <div className="activity-log-list scrollable-activity">
                {pipelineData.activity_log.slice(0, 3).map((row) => (
                  <div className="activity-log-row" key={row.id}>
                    <div>
                      <div className="meta-label">Timestamp</div>
                      <div className="meta-value">
                        {row.timestamp ? new Date(row.timestamp).toLocaleString() : 'n/a'}
                      </div>
                    </div>
                    <div className="activity-status-latency">
                      <div>
                        <div className="meta-label">Status</div>
                        <span className="status-pill status-success">
                          {row.status_code || 'saved'}
                        </span>
                      </div>
                      <div>
                        <div className="meta-label">Latency</div>
                        <div className="meta-hint">
                          {row.response_time_ms ? `${row.response_time_ms} ms` : 'n/a'}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                {pipelineData.activity_log.length > 3 && (
                  <div className="activity-scrollable">
                    {pipelineData.activity_log.slice(3).map((row) => (
                      <div className="activity-log-row" key={row.id}>
                        <div>
                          <div className="meta-label">Timestamp</div>
                          <div className="meta-value">
                            {row.timestamp ? new Date(row.timestamp).toLocaleString() : 'n/a'}
                          </div>
                        </div>
                        <div className="activity-status-latency">
                          <div>
                            <div className="meta-label">Status</div>
                            <span className="status-pill status-success">
                              {row.status_code || 'saved'}
                            </span>
                          </div>
                          <div>
                            <div className="meta-label">Latency</div>
                            <div className="meta-hint">
                              {row.response_time_ms ? `${row.response_time_ms} ms` : 'n/a'}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {pipelineData?.latest_data?.length > 0 && (
            <div className="pipeline-latest-records">
              <div className="sidebar-title">Latest extracted records</div>
              <div className="latest-records-table-wrapper">
                <table className="latest-records-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Status</th>
                      <th>Response Time</th>
                      <th>Data Preview</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...pipelineData.latest_data]
                      .sort((a, b) => {
                        const timeA = a.timestamp ? new Date(a.timestamp).getTime() : 0
                        const timeB = b.timestamp ? new Date(b.timestamp).getTime() : 0
                        return timeB - timeA // Most recent first
                      })
                      .map((row) => (
                      <tr key={row.id}>
                        <td>{row.timestamp ? new Date(row.timestamp).toLocaleString() : 'n/a'}</td>
                        <td>
                          <span className="status-pill status-success">
                            {row.status_code || 'saved'}
                          </span>
                        </td>
                        <td>{row.response_time_ms ? `${row.response_time_ms}ms` : 'n/a'}</td>
                        <td className="data-preview-cell">
                          <div className="data-preview">
                            {typeof row.data === 'string'
                              ? row.data.substring(0, 100) + (row.data.length > 100 ? '...' : '')
                              : JSON.stringify(row.data).substring(0, 100) + '...'}
                          </div>
                        </td>
                      </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default PipelineViewer

