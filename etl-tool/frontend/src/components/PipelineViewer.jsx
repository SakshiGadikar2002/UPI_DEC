import { useEffect, useMemo, useState, useRef } from 'react'
import SimpleFlow from './SimpleFlow'
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

const buildLabel = (title, status, tooltip, recordCount = null, apiName = null) => {
  const displayCount = recordCount !== null && recordCount !== undefined ? recordCount : 0
  const hasCount = recordCount !== null && recordCount !== undefined
  
  return (
    <div className="pipeline-node-label" title={tooltip || ''}>
      <div className="pipeline-node-title">{title}</div>
      <div className={`pipeline-node-status status-${status || 'pending'}`}>
        {apiName ? (
          <span className="pipeline-node-api-name">{apiName}</span>
        ) : hasCount ? (
          <span className="pipeline-node-record-count counter-animate" key={`count-${displayCount}`}>
            {displayCount.toLocaleString()} {displayCount === 1 ? 'Record' : 'Records'}
          </span>
        ) : (
          <span className="pipeline-node-status-text">{status || 'pending'}</span>
        )}
      </div>
    </div>
  )
}

function PipelineViewer({ visible = true, apiId = null, onClose = null }) {
  const apiBase = import.meta.env.VITE_API_BASE || ''
  const [selectedApi, setSelectedApi] = useState(apiId || '')
  const [pipelineData, setPipelineData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [options, setOptions] = useState([])
  const [showFitViewModal, setShowFitViewModal] = useState(false)
  const [isTriggering, setIsTriggering] = useState(false)
  
  // Refs must be declared before any hooks that use them
  const currentRunIdRef = useRef(null)
  const baselineCountsRef = useRef({}) // Track baseline counts when run starts
  
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

  // Function to trigger/start the pipeline for an API
  const triggerPipelineRun = async (apiIdToTrigger, showLoading = false) => {
    if (!apiIdToTrigger) return false
    if (showLoading) setIsTriggering(true)
    try {
      // Try to start the connector/pipeline
      const startResp = await fetch(`${apiBase}/api/connectors/${apiIdToTrigger}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (startResp.ok) {
        console.log(`[PipelineViewer] Successfully triggered pipeline for ${apiIdToTrigger}`)
        // Wait a moment for the run to initialize, then refresh
        setTimeout(() => {
          fetchPipeline(apiIdToTrigger, { mode: 'full' })
        }, 1000)
        if (showLoading) setIsTriggering(false)
        return true
      } else {
        // If connector start fails, try to trigger via job scheduler
        const jobResp = await fetch(`${apiBase}/api/jobs/${apiIdToTrigger}/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        if (jobResp.ok) {
          console.log(`[PipelineViewer] Successfully triggered job for ${apiIdToTrigger}`)
          // Wait a moment for the run to initialize, then refresh
          setTimeout(() => {
            fetchPipeline(apiIdToTrigger, { mode: 'full' })
          }, 1000)
          if (showLoading) setIsTriggering(false)
          return true
        }
      }
      if (showLoading) setIsTriggering(false)
      return false
    } catch (err) {
      console.warn(`[PipelineViewer] Could not trigger pipeline for ${apiIdToTrigger}:`, err)
      if (showLoading) setIsTriggering(false)
      return false
    }
  }

  const fetchPipeline = async (apiIdToFetch, opts = {}) => {
    const silent = !!opts.silent
    const mode = opts.mode || 'full'
    const autoTrigger = !!opts.autoTrigger
    if (!apiIdToFetch) return
    if (!silent) setLoading(true)
    setError('')
    try {
      // Add cache-busting timestamp to ensure fresh data on every request
      const timestamp = Date.now()
      let resp = await fetch(`${apiBase}/api/etl/pipeline/${apiIdToFetch}?t=${timestamp}`, {
        cache: 'no-cache',
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        }
      })
      if (!resp.ok) {
        resp = await fetch(`${apiBase}/api/pipeline/${apiIdToFetch}?t=${timestamp}`, {
          cache: 'no-cache',
          headers: {
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
          }
        })
      }
      if (!resp.ok) {
        throw new Error(`Pipeline endpoint returned ${resp.status}`)
      }
      const data = await resp.json()
      
      // If autoTrigger is enabled, ensure pipeline execution starts
      // When "View Pipeline" is clicked, always trigger execution if no active run exists
      if (autoTrigger && data?.api) {
        const hasActiveRun = data?.current_run && 
          (data.current_run.status === 'running' || data.current_run.status === 'in_progress')
        const hasRecentRun = data?.history?.[0] && 
          new Date(data.history[0].started_at) > new Date(Date.now() - 30000) // Run in last 30 seconds
        
        // Always trigger if no active run exists (even if recent run exists, start fresh)
        // This ensures "View Pipeline" always shows live execution
        if (!hasActiveRun) {
          console.log('[PipelineViewer] No active run found, triggering new pipeline execution...')
          triggerPipelineRun(apiIdToFetch, false).then((success) => {
            if (success) {
              // Wait a bit for the run to start, then fetch again
              setTimeout(() => {
                fetchPipeline(apiIdToFetch, { silent: true, mode: 'full' })
              }, 1500)
            }
          })
        } else {
          console.log('[PipelineViewer] Active run already in progress, monitoring...')
        }
      }
      
      // Extract record counts from the response - prioritize step details for accurate counts
      const extractCounts = (data) => {
        const out = {}
        const ds = data?.data_stats || {}
        const steps = data?.current_run?.steps || data?.history?.[0]?.steps || []
        
        console.log('[ExtractCounts] 🔍 Starting extraction - data_stats:', ds)
        console.log('[ExtractCounts] 🔍 Steps available:', steps.map(s => ({
          name: s?.step_name || s?.stepName,
          status: s?.status,
          hasDetails: !!s?.details
        })))
        
        // If we have steps, extract counts from them
        if (steps.length > 0) {
          steps.forEach((step) => {
            const stepName = step?.step_name || step?.stepName
            if (!stepName) return
            
            // Skip source and destination - we only want extract, transform, load
            if (stepName === 'source' || stepName === 'destination') return
            
            let recordCount = null
            let source = 'none'
            
            // For EXTRACT step: Prioritize data_stats.total_records (cumulative count from api_connector_data)
            // This ensures we show cumulative records across all runs, not just the latest run's item count
            if (stepName === 'extract' && ds.total_records !== undefined && ds.total_records !== null) {
              recordCount = ds.total_records
              source = 'data_stats.total_records'
            }
            // For TRANSFORM step: Show count from current run only (not cumulative)
            // Calculate by subtracting baseline count from current total_items
            else if (stepName === 'transform') {
              // Only calculate current run count if we have an active run
              const hasActiveRun = data?.current_run && (data.current_run.status === 'running' || data.current_run.status === 'in_progress')
              if (hasActiveRun || currentRunIdRef.current) {
                const baseline = baselineCountsRef.current.transform || 0
                const currentTotal = ds.total_items !== undefined && ds.total_items !== null ? ds.total_items : 0
                recordCount = Math.max(0, currentTotal - baseline)
                source = 'data_stats.total_items (current run)'
                console.log(`[ExtractCounts] Transform: baseline=${baseline}, current=${currentTotal}, run_count=${recordCount}`)
              } else {
                // No active run - fall through to step details or other fallbacks
                recordCount = null
              }
            }
            // For LOAD step: Use data_stats.total_records (cumulative count)
            else if (stepName === 'load' && ds.total_records !== undefined && ds.total_records !== null) {
              recordCount = ds.total_records
              source = 'data_stats.total_records'
            }
            // Fallback 1: Try to extract count from step details (for other steps or if data_stats not available)
            else if (step?.details) {
              try {
                const details = typeof step.details === 'string' ? JSON.parse(step.details) : step.details
                recordCount = details.records || details.items || details.count || details.record_count || 
                             details.processed || details.total_processed || null
                if (recordCount !== null) source = 'step_details'
                console.log(`[ExtractCounts] Step ${stepName} details:`, details, '-> count:', recordCount)
              } catch (e) {
                console.warn(`[ExtractCounts] Failed to parse details for ${stepName}:`, e)
              }
            }
            
            // Fallback 2: Check if step has a direct count property
            if ((recordCount === null || recordCount === undefined) && step.record_count !== undefined) {
              recordCount = step.record_count
              source = 'step.record_count'
            }
            
            // Always include count if we found one (including 0)
            if (recordCount !== null && recordCount !== undefined) {
              const numCount = Number(recordCount)
              if (!isNaN(numCount)) {
                out[stepName] = Math.max(0, numCount) // Ensure non-negative
                console.log(`[ExtractCounts] ✅ ${stepName}: ${out[stepName]} (from ${source})`)
              } else {
                console.warn(`[ExtractCounts] ⚠️ ${stepName}: Invalid number ${recordCount}`)
              }
            } else {
              console.log(`[ExtractCounts] ❌ ${stepName}: No count found`)
            }
          })
        } else {
          // No steps available - extract directly from data_stats (for non-real-time APIs)
          // This ensures background updates are reflected even without an active run
          console.log('[ExtractCounts] No steps found, extracting from data_stats only')
          if (ds.total_records !== undefined && ds.total_records !== null) {
            // For non-real-time APIs, total_records might represent all steps
            out['extract'] = Math.max(0, Number(ds.total_records))
            out['load'] = Math.max(0, Number(ds.total_records))
            console.log(`[ExtractCounts] ✅ extract/load: ${out['extract']} (from data_stats.total_records)`)
          }
          if (ds.total_items !== undefined && ds.total_items !== null) {
            out['transform'] = Math.max(0, Number(ds.total_items))
            console.log(`[ExtractCounts] ✅ transform: ${out['transform']} (from data_stats.total_items)`)
          }
        }
        
        console.log('[ExtractCounts] 📊 Final extracted counts:', out)
        return out
      }
      
      if (mode === 'full') {
        // Use functional update to prevent unnecessary re-renders and flickering
        setPipelineData(prevData => {
          // Only update if data actually changed to prevent flickering
          if (prevData && JSON.stringify(prevData.current_run?.run_id) === JSON.stringify(data.current_run?.run_id) && 
              JSON.stringify(prevData.data_stats) === JSON.stringify(data.data_stats) &&
              JSON.stringify(prevData.current_run?.status) === JSON.stringify(data.current_run?.status)) {
            // Data hasn't changed significantly, return previous to prevent flicker
            return prevData
          }
          return data
        })
        const counts = extractCounts(data)
        console.log('[PipelineViewer] Full mode - extracted counts:', counts)
        
        // Always update record targets in full mode to ensure counts are current
        setRecordTargets(prevTargets => {
          // Merge with previous to preserve any ongoing animations
          const merged = { ...prevTargets, ...counts }
          // Only update if counts actually changed
          const hasChanges = Object.keys(counts).some(key => counts[key] !== prevTargets[key])
          if (!hasChanges && Object.keys(prevTargets).length > 0) {
            return prevTargets // Return previous to prevent unnecessary re-render
          }
          console.log('[PipelineViewer] Full mode - setting record targets:', merged)
          return merged
        })
      } else {
        // For 'counts' mode, merge the new step data into existing pipelineData
        // so that stepRecordCounts can recalculate with fresh data
        setPipelineData((prevData) => {
          if (!prevData) return data
          
          // Always update data_stats first to ensure latest counts are available
          const newDataStats = data.data_stats || {}
          const prevDataStats = prevData.data_stats || {}
          
          // Check if data_stats actually changed (for non-real-time APIs that update in background)
          const dataStatsChanged = JSON.stringify(newDataStats) !== JSON.stringify(prevDataStats)
          
          if (dataStatsChanged) {
            console.log('[PipelineViewer] 🔄 data_stats changed:', {
              previous: prevDataStats,
              new: newDataStats
            })
          }
          
          // Merge the current_run steps if they exist
          if (data?.current_run?.steps) {
            const merged = {
              ...prevData,
              current_run: {
                ...prevData.current_run,
                ...data.current_run,
                steps: data.current_run.steps, // Use the new steps data
              },
              data_stats: newDataStats, // Always use new data_stats
            }
            console.log('[PipelineViewer] Counts mode - merged pipelineData:', {
              steps: merged.current_run?.steps,
              data_stats: merged.data_stats,
              dataStatsChanged
            })
            return merged
          }
          
          // If no current_run, update data_stats at least (important for non-real-time APIs)
          // This ensures background updates are reflected even without an active run
          return {
            ...prevData,
            data_stats: newDataStats, // Always use new data_stats
          }
        })
        
        const counts = extractCounts(data)
        console.log('[PipelineViewer] Counts mode - extracted counts:', counts)
        
        // ALWAYS update recordTargets to ensure UI reflects latest counts from backend
        // This is critical for real-time updates
        setRecordTargets(prevTargets => {
          const hasChanges = Object.keys(counts).some(
            key => counts[key] !== prevTargets[key]
          ) || Object.keys(prevTargets).some(
            key => !counts.hasOwnProperty(key) && prevTargets[key] !== undefined
          )
          
          // Always merge new counts - this ensures backend updates are reflected
          const updated = { ...prevTargets, ...counts }
          
          // Log changes for debugging
          Object.keys(counts).forEach(key => {
            if (counts[key] !== prevTargets[key]) {
              console.log(`[PipelineViewer] 🔄 COUNT CHANGED: ${key} ${prevTargets[key]} -> ${counts[key]}`)
            }
          })
          
          console.log('[PipelineViewer] Counts mode - updating record targets:', {
            previous: prevTargets,
            new: counts,
            merged: updated,
            hasChanges
          })
          return updated
        })
      }
    } catch (err) {
      console.error('Failed to fetch pipeline', err)
      setError(err.message || 'Unable to load pipeline')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  useEffect(() => {
    if (!visible) return undefined
    if (!selectedApi) {
      setPipelineData(null)
      return undefined
    }
    
    // When "View Pipeline" is clicked, immediately trigger pipeline execution
    // This ensures the UI shows live execution state from the start
    const initialFetch = async () => {
      console.log('[PipelineViewer] Initial fetch - triggering pipeline execution for:', selectedApi)
      // Always trigger execution when viewer opens to show live state
      await fetchPipeline(selectedApi, { mode: 'full', autoTrigger: true })
    }
    initialFetch()
    
    let tick = 0
    console.log('[PipelineViewer] Starting real-time polling for API:', selectedApi)
    
    // Use 500ms polling interval for more responsive real-time updates
    // This ensures UI stays synchronized with backend execution state
    const interval = setInterval(() => {
      if (!visible || !selectedApi) {
        console.log('[PipelineViewer] Skipping poll - visible:', visible, 'selectedApi:', selectedApi)
        return
      }
      
      tick += 1
      
      // Fetch counts every 500ms for real-time counter updates
      // This ensures Extract, Transform, and Load counts update smoothly as records are processed
      fetchPipeline(selectedApi, { silent: true, mode: 'counts' }).then(() => {
        // Only log every 10 ticks to reduce console noise
        if (tick % 10 === 0) {
          console.log(`[PipelineViewer] Real-time polling active - tick ${tick}`)
        }
      }).catch(err => {
        console.error(`[PipelineViewer] Error fetching counts at tick ${tick}:`, err)
      })
      
      // Fetch full data every 3 seconds (every 6 ticks at 500ms interval) to get complete state
      // This includes step statuses, run status, and all metadata
      // Reduced frequency to prevent flickering
      if (tick % 6 === 0) {
        fetchPipeline(selectedApi, { silent: true, mode: 'full' })
      }
    }, 500) // Poll every 500ms for real-time synchronization with backend
    
    return () => {
      console.log('[PipelineViewer] Clearing polling interval')
      clearInterval(interval)
    }
  }, [selectedApi, visible, apiBase])

  // Compute step sequence first (needed by stepStatuses)
  const stepSequence = useMemo(() => {
    // Get steps from current run, or fallback to latest history run if no current run
    const steps = pipelineData?.current_run?.steps || 
                  pipelineData?.history?.[0]?.steps || 
                  []
    
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
        .filter((name) => name !== 'clean')
      
      if (stepNames.length > 0) {
        return stepNames
      }
    }
    return fallbackSteps
  }, [pipelineData])

  const stepStatuses = useMemo(() => {
    const statuses = {}
    // Get steps from current run (prioritize active run), or fallback to latest history run
    const steps = pipelineData?.current_run?.steps || 
                  pipelineData?.history?.[0]?.steps || 
                  []
    
    // Normalize status values from backend to match our status colors
    const normalizeStatus = (status) => {
      if (!status) return 'pending'
      const normalized = status.toLowerCase()
      // Map various backend status values to our standard statuses
      if (normalized === 'running' || normalized === 'in_progress' || normalized === 'in-progress') {
        return 'running'
      }
      if (normalized === 'success' || normalized === 'completed' || normalized === 'done') {
        return 'success'
      }
      if (normalized === 'failure' || normalized === 'failed' || normalized === 'error') {
        return 'failure'
      }
      return normalized || 'pending'
    }
    
    steps.forEach((step) => {
      // Handle both step_name and stepName (camelCase) field names
      const stepName = step?.step_name || step?.stepName
      if (step && stepName) {
        // Use normalized status to ensure consistent UI representation
        statuses[stepName] = normalizeStatus(step.status)
      } else {
        console.warn('StepStatuses - Skipping invalid step:', step)
      }
    })
    
    // For steps in sequence that don't have status yet, mark as pending
    // This ensures upcoming steps show as pending
    stepSequence.forEach((stepName) => {
      if (!statuses.hasOwnProperty(stepName)) {
        statuses[stepName] = 'pending'
      }
    })
    
    return statuses
  }, [pipelineData, stepSequence])

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
        
        // For EXTRACT step: Prioritize data_stats.total_records (cumulative count from api_connector_data)
        if (stepName === 'extract' && dataStats.total_records !== undefined && dataStats.total_records !== null) {
          recordCount = dataStats.total_records
        }
        // For TRANSFORM step: Show count from current run only (not cumulative)
        // Calculate by subtracting baseline count from current total_items
        else if (stepName === 'transform') {
          // Only calculate current run count if we have an active run
          const hasActiveRun = pipelineData?.current_run && (pipelineData.current_run.status === 'running' || pipelineData.current_run.status === 'in_progress')
          if (hasActiveRun || currentRunIdRef.current) {
            const baseline = baselineCountsRef.current.transform || 0
            const currentTotal = dataStats.total_items !== undefined && dataStats.total_items !== null ? dataStats.total_items : 0
            recordCount = Math.max(0, currentTotal - baseline)
          } else {
            // No active run - fall through to step details or other fallbacks
            recordCount = null
          }
        }
        // For LOAD step: Use data_stats.total_records (cumulative count)
        else if (stepName === 'load' && dataStats.total_records !== undefined && dataStats.total_records !== null) {
          recordCount = dataStats.total_records
        }
        // Fallback: Try to extract count from step details
        else if (step.details) {
          try {
            const details = typeof step.details === 'string' ? JSON.parse(step.details) : step.details
            recordCount = details.records || details.items || details.count || details.record_count || null
          } catch (e) {
            // Keep null if parsing fails
          }
        }
        
        // Fallback: Check if step has a direct record_count property
        if ((recordCount === null || recordCount === undefined) && step.record_count !== undefined) {
          recordCount = step.record_count
        }
        
        // Include count even if it's 0 (0 is a valid count, not missing data)
        if (recordCount !== null && recordCount !== undefined) {
          counts[stepName] = Number(recordCount) || 0
        }
      }
    })
    
    return counts
  }, [pipelineData])

  const activeStep = useMemo(() => {
    if (!pipelineData?.current_run) {
      console.log('[ActiveStep] No current_run found')
      return null
    }
    
    const steps = pipelineData.current_run.steps || []
    const runStatus = pipelineData.current_run.status
    
    // Create a map of step_name -> step data for quick lookup
    const stepMap = new Map()
    steps.forEach((s) => {
      const stepName = s?.step_name || s?.stepName
      if (stepName) {
        stepMap.set(stepName, s)
      }
    })
    
    console.log('[ActiveStep] Checking steps:', {
      runStatus,
      stepsCount: steps.length,
      stepSequence,
      steps: steps.map(s => ({
        name: s?.step_name || s?.stepName,
        status: s?.status,
        started: s?.started_at,
        completed: s?.completed_at
      }))
    })
    
    // Iterate through steps in the correct pipeline order (extract -> transform -> load)
    // This ensures we check steps in sequence, not in array order
    for (const stepName of stepSequence) {
      const step = stepMap.get(stepName)
      if (!step) continue
      
      const status = (step?.status || '').toLowerCase()
      const hasStarted = step?.started_at && step.started_at !== null
      const notCompleted = !step?.completed_at || step.completed_at === null
      
      // Priority 1: Step is explicitly marked as running
      if (status === 'running' || status === 'in_progress') {
        console.log('[ActiveStep] Found running step (by status):', stepName)
        return stepName
      }
      
      // Priority 2: Step has started but not completed
      if (hasStarted && notCompleted) {
        console.log('[ActiveStep] Found in-progress step (started but not completed):', stepName)
        return stepName
      }
    }
    
    // Priority 3: If pipeline is running but no step is marked as running,
    // find the first incomplete step in sequence order
    if (runStatus === 'running' || runStatus === 'in_progress') {
      for (const stepName of stepSequence) {
        const step = stepMap.get(stepName)
        if (!step) continue
        
        const notCompleted = !step?.completed_at || step.completed_at === null
        if (notCompleted) {
          console.log('[ActiveStep] Found pending step (first incomplete in sequence):', stepName)
          return stepName
        }
      }
    }
    
    console.log('[ActiveStep] No active step found')
    return null
  }, [pipelineData, stepSequence])

  const [animatedCounts, setAnimatedCounts] = useState({})
  const [recordTargets, setRecordTargets] = useState({})
  const [renderTick, setRenderTick] = useState(0)
  const targetsRef = useRef({})
  const timersRef = useRef({})
  
  // Reset counts to 0 when a new pipeline run starts and capture baseline
  useEffect(() => {
    const currentRunId = pipelineData?.current_run?.run_id || pipelineData?.current_run?.id
    const dataStats = pipelineData?.data_stats || {}
    
    if (currentRunId && currentRunId !== currentRunIdRef.current) {
      // New run detected - capture baseline counts and reset animated counts to 0
      currentRunIdRef.current = currentRunId
      
      // Store baseline counts for calculating current run increments
      baselineCountsRef.current = {
        transform: dataStats.total_items || 0,
        extract: dataStats.total_records || 0,
        load: dataStats.total_records || 0
      }
      
      const resetCounts = {}
      stepSequence.forEach((stepName) => {
        resetCounts[stepName] = 0
      })
      setAnimatedCounts(resetCounts)
      setRecordTargets({})
      targetsRef.current = {}
      // Cancel any ongoing animations
      Object.keys(timersRef.current).forEach((k) => {
        if (timersRef.current[k]) {
          cancelAnimationFrame(timersRef.current[k])
          timersRef.current[k] = null
        }
      })
    }
  }, [pipelineData?.current_run?.run_id, pipelineData?.current_run?.id, stepSequence, pipelineData?.data_stats])
  
  useEffect(() => {
    if (!recordTargets || Object.keys(recordTargets).length === 0) {
      // If no targets but we have animated counts, keep them
      return
    }
    
    console.log('[Animation] Processing recordTargets:', recordTargets)
    console.log('[Animation] Current animatedCounts:', animatedCounts)
    
    Object.keys(recordTargets).forEach((key) => {
      const target = typeof recordTargets[key] === 'number' ? recordTargets[key] : 0
      const prevTarget = targetsRef.current[key]
      const currentValue = typeof animatedCounts[key] === 'number' ? animatedCounts[key] : 0
      
      // ALWAYS update if target is different from previous target OR current animated value
      // This ensures even small increments are visible
      if (prevTarget !== target || currentValue !== target) {
        console.log(`[Animation] Updating ${key}: ${currentValue} -> ${target} (prevTarget: ${prevTarget})`)
        
        // Update target reference immediately
        targetsRef.current[key] = target
        
        // Cancel any existing animation for this key
        if (timersRef.current[key]) {
          cancelAnimationFrame(timersRef.current[key])
          timersRef.current[key] = null
        }
        
        const start = currentValue
        const startTime = performance.now()
        
        // For very small changes (1-2 records), make animation very fast
        const diff = Math.abs(target - start)
        const duration = diff === 0 ? 0 : Math.max(100, Math.min(400, diff * 8))
        
        if (duration === 0 || diff === 0) {
          // No animation needed, update immediately
          setAnimatedCounts(prev => {
            const updated = { ...prev, [key]: target }
            console.log(`[Animation] Immediate update for ${key}:`, updated)
            return updated
          })
          return
        }
        
        const animate = (now) => {
          const elapsed = now - startTime
          const t = Math.min(1, elapsed / duration)
          
          // Smooth easing function for natural counter feel
          const eased = t < 0.5 
            ? 2 * t * t 
            : -1 + (4 - 2 * t) * t
          
          const value = Math.round(start + (target - start) * eased)
          
          setAnimatedCounts(prev => {
            const updated = { ...prev, [key]: Math.max(0, value) }
            return updated
          })
          
          if (t < 1) {
            timersRef.current[key] = requestAnimationFrame(animate)
          } else {
            // Ensure we end exactly at target
            setAnimatedCounts(prev => {
              const final = { ...prev, [key]: target }
              console.log(`[Animation] Completed for ${key}:`, final)
              // Force a re-render by updating renderTick
              setRenderTick(prev => prev + 1)
              return final
            })
            timersRef.current[key] = null
          }
        }
        
        timersRef.current[key] = requestAnimationFrame(animate)
      }
    })
    
    return () => {
      Object.keys(timersRef.current).forEach((k) => {
        if (timersRef.current[k]) {
          cancelAnimationFrame(timersRef.current[k])
          timersRef.current[k] = null
        }
      })
    }
  }, [recordTargets])

  const selectedMeta = options.find((a) => a.id === selectedApi)

  const nodes = useMemo(() => {
    const flowNodes = []
    const positionList = (count) => Array.from({ length: count }, (_, idx) => ({ x: idx * 220 + 20, y: 80 }))
    const positions = positionList(stepSequence.length + 2)

    const destinationStatus = stepStatuses[stepSequence[stepSequence.length - 1]] || 'pending'
    const dataStats = pipelineData?.data_stats || {}
    
    // Get source record count (from first step or data_stats) - use animated count for smooth counter
    const sourceRecordCount = stepSequence.length > 0 
      ? (animatedCounts[stepSequence[0]] ?? stepRecordCounts[stepSequence[0]] ?? null)
      : (pipelineData?.data_stats?.total_records ?? null)
    
    // Get destination record count (from last step or data_stats) - use animated count for smooth counter
    const destinationRecordCount = stepSequence.length > 0
      ? (animatedCounts[stepSequence[stepSequence.length - 1]] ?? stepRecordCounts[stepSequence[stepSequence.length - 1]] ?? null)
      : (pipelineData?.data_stats?.total_records ?? null)

    console.log('Building nodes - stepSequence:', stepSequence)
    console.log('Building nodes - stepStatuses:', stepStatuses)

    // Source node - show API name (prioritize API name, fallback to record count if no API name)
    const apiName = pipelineData?.api?.api_name || selectedMeta?.name || null
    // Source should never be highlighted as active - only actual pipeline steps can be active
    const isSourceActive = false
    // Only show record count in Source if API name is not available
    const sourceDisplayCount = apiName ? null : sourceRecordCount
    
    flowNodes.push({
      id: 'source',
      data: { 
        label: buildLabel('Source', 'pending', pipelineData?.api?.source_url, sourceDisplayCount, apiName),
        apiName: apiName 
      },
      position: positions[0],
      style: { 
        ...defaultNodeStyle, 
        borderColor: isSourceActive ? '#2563eb' : statusColors.pending, 
        background: isSourceActive ? '#DBEAFE' : '#F3F4F6',
        boxShadow: isSourceActive ? '0 0 12px rgba(37, 99, 235, 0.5)' : 'none',
        transition: 'all 0.3s ease',
      },
      className: isSourceActive ? 'pipeline-node-active' : '',
    })

    stepSequence.forEach((stepName, idx) => {
      if (!stepName) {
        console.warn(`Skipping empty stepName at index ${idx}`)
        return // Skip if stepName is empty
      }
      const status = stepStatuses[stepName] || 'pending'
      
      // Get record count using the same logic as step timeline for consistency
      // For EXTRACT: Prioritize data_stats.total_records (cumulative count from api_connector_data)
      const stepInfo = pipelineData?.current_run?.steps?.find((s) => (s?.step_name || s?.stepName) === stepName) ||
                      pipelineData?.history?.[0]?.steps?.find((s) => (s?.step_name || s?.stepName) === stepName) ||
                      null
      
      let recordCount = null
      // For EXTRACT step: Prioritize data_stats.total_records (cumulative count)
      if (stepName === 'extract' && dataStats.total_records !== undefined && dataStats.total_records !== null) {
        recordCount = dataStats.total_records
      }
      // For TRANSFORM step: Show count from current run only (not cumulative)
      // Calculate by subtracting baseline count from current total_items
      else if (stepName === 'transform') {
        // Only calculate current run count if we have an active run
        const hasActiveRun = pipelineData?.current_run && (pipelineData.current_run.status === 'running' || pipelineData.current_run.status === 'in_progress')
        if (hasActiveRun || currentRunIdRef.current) {
          const baseline = baselineCountsRef.current.transform || 0
          const currentTotal = dataStats.total_items !== undefined && dataStats.total_items !== null ? dataStats.total_items : 0
          recordCount = Math.max(0, currentTotal - baseline)
        } else {
          // No active run - fall through to step details or other fallbacks
          recordCount = null
        }
      }
      // For LOAD step: Use data_stats.total_records (cumulative count)
      else if (stepName === 'load' && dataStats.total_records !== undefined && dataStats.total_records !== null) {
        recordCount = dataStats.total_records
      }
      // Fallback: Try to get from step details
      else if (stepInfo?.details) {
        try {
          const details = typeof stepInfo.details === 'string' ? JSON.parse(stepInfo.details) : stepInfo.details
          recordCount = details.records || details.items || details.count || details.record_count || null
        } catch (e) {
          // Keep null if parsing fails
        }
      }
      
      // Use animated count if available for smooth counter, otherwise use the extracted count
      // Always prefer animatedCounts for real-time updates
      const finalCount = animatedCounts[stepName] !== undefined 
        ? animatedCounts[stepName] 
        : (recordCount !== null && recordCount !== undefined ? recordCount : 0)
      
      // Log for debugging (only when count changes to avoid spam)
      if (finalCount > 0) {
        console.log(`[Nodes] Step ${stepName}: animatedCount=${animatedCounts[stepName]}, recordCount=${recordCount}, finalCount=${finalCount}`)
      }
      
      const displayName = stepName ? stepName.toUpperCase() : 'UNKNOWN'
      // Use finalCount as key to force re-render when count changes
      const labelElement = buildLabel(displayName, status, pipelineData?.api?.api_name, finalCount)
      
      const isActive = activeStep && stepName === activeStep
      if (isActive) {
        console.log(`[Active Step] Highlighting step: ${stepName}`, {
          activeStep,
          stepName,
          status,
          recordCount: finalCount
        })
      }
      const baseStyle = {
        ...defaultNodeStyle,
        borderColor: statusColors[status] || statusColors.pending,
        background: `${statusColors[status] || statusColors.pending}20`,
      }
      const activeStyle = isActive
        ? { 
            ...baseStyle, 
            borderColor: '#2563eb', 
            background: '#DBEAFE',
            boxShadow: '0 0 12px rgba(37, 99, 235, 0.5)',
            borderWidth: 3,
            transition: 'all 0.3s ease',
          }
        : baseStyle

      flowNodes.push({
        id: stepName || `step-${idx}`,
        data: { label: labelElement },
        position: positions[idx + 1],
        style: activeStyle,
        className: isActive ? 'pipeline-node-active' : '',
      })
    })

    // Destination node - show record count
    // Destination should never be highlighted as active - only actual pipeline steps can be active
    const isDestinationActive = false
    
    flowNodes.push({
      id: 'destination',
      data: { label: buildLabel('Destination', destinationStatus, pipelineData?.api?.destination, destinationRecordCount) },
      position: positions[positions.length - 1],
      style: {
        ...defaultNodeStyle,
        borderColor: isDestinationActive ? '#2563eb' : (statusColors[destinationStatus] || statusColors.pending),
        background: isDestinationActive ? '#DBEAFE' : '#ECFDF3',
        boxShadow: isDestinationActive ? '0 0 12px rgba(37, 99, 235, 0.5)' : 'none',
        transition: 'all 0.3s ease',
      },
      className: isDestinationActive ? 'pipeline-node-active' : '',
    })

    console.log('Final nodes array:', flowNodes)
    return flowNodes
  }, [pipelineData, stepStatuses, stepSequence, animatedCounts, activeStep, stepRecordCounts, selectedMeta, renderTick])

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
              <button
                className="pipeline-refresh"
                onClick={() => triggerPipelineRun(selectedApi, true)}
                disabled={!selectedApi || isTriggering}
                title="Start/Run the pipeline for this API"
              >
                {isTriggering ? 'Starting...' : 'Run Pipeline'}
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
                <SimpleFlow nodes={nodes} edges={edges} />
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
                      <SimpleFlow nodes={nodes} edges={edges} />
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
                {pipelineData?.history?.slice(0, 3).map((run) => {
                  let timestamp = '-'
                  if (run.started_at) {
                    try {
                      const date = new Date(run.started_at)
                      if (!isNaN(date.getTime())) {
                        timestamp = date.toLocaleTimeString('en-US', { 
                          hour: '2-digit', 
                          minute: '2-digit', 
                          second: '2-digit', 
                          hour12: false 
                        })
                      }
                    } catch (e) {
                      console.warn('Invalid date format:', run.started_at)
                    }
                  }
                  return (
                    <div key={run.run_id} className="history-item">
                      <div className="history-row">
                        <span className={`status-pill status-${run.status}`}>{run.status}</span>
                        <span className="history-time">{timestamp}</span>
                      </div>
                      <div className="history-hint">
                        {run.duration_seconds ? `${run.duration_seconds.toFixed(1)}s` : 'in progress'}
                        {run.error_message ? ` • ${run.error_message}` : ''}
                      </div>
                    </div>
                  )
                })}
                {pipelineData?.history?.length > 3 && (
                  <div className="history-scrollable">
                    {pipelineData.history.slice(3).map((run) => {
                      let timestamp = '-'
                      if (run.started_at) {
                        try {
                          const date = new Date(run.started_at)
                          if (!isNaN(date.getTime())) {
                            timestamp = date.toLocaleTimeString('en-US', { 
                              hour: '2-digit', 
                              minute: '2-digit', 
                              second: '2-digit', 
                              hour12: false 
                            })
                          }
                        } catch (e) {
                          console.warn('Invalid date format:', run.started_at)
                        }
                      }
                      return (
                        <div key={run.run_id} className="history-item">
                          <div className="history-row">
                            <span className={`status-pill status-${run.status}`}>{run.status}</span>
                            <span className="history-time">{timestamp}</span>
                          </div>
                          <div className="history-hint">
                            {run.duration_seconds ? `${run.duration_seconds.toFixed(1)}s` : 'in progress'}
                            {run.error_message ? ` • ${run.error_message}` : ''}
                          </div>
                        </div>
                      )
                    })}
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
                
                // Extract count from details or data_stats - use same logic as canvas nodes
                let countDisplay = '—'
                
                // For EXTRACT step: Prioritize data_stats.total_records (cumulative count from api_connector_data)
                let recordCount = null
                if (stepName === 'extract' && dataStats.total_records !== undefined && dataStats.total_records !== null) {
                  recordCount = dataStats.total_records
                }
                // For TRANSFORM step: Show count from current run only (not cumulative)
                // Calculate by subtracting baseline count from current total_items
                else if (stepName === 'transform') {
                  // Only calculate current run count if we have an active run
                  const hasActiveRun = pipelineData?.current_run && (pipelineData.current_run.status === 'running' || pipelineData.current_run.status === 'in_progress')
                  if (hasActiveRun || currentRunIdRef.current) {
                    const baseline = baselineCountsRef.current.transform || 0
                    const currentTotal = dataStats.total_items !== undefined && dataStats.total_items !== null ? dataStats.total_items : 0
                    recordCount = Math.max(0, currentTotal - baseline)
                  } else {
                    // No active run - fall through to step details or other fallbacks
                    recordCount = null
                  }
                }
                // For LOAD step: Use data_stats.total_records (cumulative count)
                else if (stepName === 'load' && dataStats.total_records !== undefined && dataStats.total_records !== null) {
                  recordCount = dataStats.total_records
                }
                // Fallback: Try to get from step details
                else if (stepInfo?.details) {
                  try {
                    const parsed = typeof details === 'string' ? JSON.parse(details) : details
                    recordCount = parsed.records || parsed.items || parsed.count || parsed.record_count || null
                  } catch (e) {
                    // Keep null if parsing fails
                  }
                }
                
                // Use animated count if available for consistency with canvas
                const finalCount = animatedCounts[stepName] !== undefined 
                  ? animatedCounts[stepName] 
                  : recordCount
                
                if (finalCount !== null && finalCount !== undefined) {
                  countDisplay = `${finalCount}`
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

