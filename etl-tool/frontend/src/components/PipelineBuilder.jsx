import { useState, useRef, useEffect, useCallback } from 'react'
import SimpleFlow from './SimpleFlow'
import VisualizationParametersPanel from './VisualizationParametersPanel'
import PipelineVisualization from './PipelineVisualization'
import './PipelineBuilder.css'

const NODE_TYPES = {
  source: { label: 'Source', icon: '📥', color: '#3B82F6' },
  field_selector: { label: 'Field Selector', icon: '📋', color: '#10B981' },
  filter: { label: 'Filter', icon: '🔍', color: '#F59E0B' },
  transform: { label: 'Transform', icon: '⚙️', color: '#78176b' },
  destination: { label: 'Destination', icon: '💾', color: '#EF4444' }
}

function PipelineBuilder({ onClose, pipelineId = null }) {
  const apiBase = import.meta.env.VITE_API_BASE || ''
  const [nodes, setNodes] = useState([])
  const [edges, setEdges] = useState([])
  const [selectedNode, setSelectedNode] = useState(null)
  const [connectors, setConnectors] = useState([])
  const [availableFields, setAvailableFields] = useState([])
  const [pipelineName, setPipelineName] = useState('')
  const [pipelineDescription, setPipelineDescription] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [nextNodeId, setNextNodeId] = useState(1)
  const [connectingFrom, setConnectingFrom] = useState(null)
  const [showPipelineList, setShowPipelineList] = useState(false)
  const [showResults, setShowResults] = useState(false)
  const [pipelineResults, setPipelineResults] = useState(null)
  const [activeTab, setActiveTab] = useState('canvas') // 'canvas' | 'results'
  const [currentPipelineId, setCurrentPipelineId] = useState(pipelineId)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [history, setHistory] = useState([])
  const [future, setFuture] = useState([])
  const [visualizationConfig, setVisualizationConfig] = useState({
    selected_fields: [],
    order: [],
    visibility: {}
  })
  const [hoveredNodeId, setHoveredNodeId] = useState(null)
  const containerRef = useRef(null)
  const pipelineBuilderRef = useRef(null)
  const nodesRef = useRef([])
  const edgesRef = useRef([])
  const undoRef = useRef(() => {})
  const redoRef = useRef(() => {})
  
  // Keep refs in sync with state
  useEffect(() => {
    nodesRef.current = nodes
    edgesRef.current = edges
  }, [nodes, edges])

  // Define history functions early to avoid initialization issues
  const pushHistory = () => {
    setHistory(prev => [...prev.slice(-19), { nodes: JSON.parse(JSON.stringify(nodesRef.current)), edges: JSON.parse(JSON.stringify(edgesRef.current)) }])
    setFuture([])
  }

  const undo = () => {
    setHistory(prev => {
      if (prev.length === 0) return prev
      const previous = prev[prev.length - 1]
      // Get current state before updating
      setNodes(currentNodes => {
        setEdges(currentEdges => {
          setFuture(fut => [...fut, { nodes: JSON.parse(JSON.stringify(currentNodes)), edges: JSON.parse(JSON.stringify(currentEdges)) }])
          return previous.edges
        })
        return previous.nodes
      })
      setSelectedNode(null)
      return prev.slice(0, -1)
    })
  }

  const redo = () => {
    setFuture(prev => {
      if (prev.length === 0) return prev
      const next = prev[prev.length - 1]
      // Get current state before updating
      setNodes(currentNodes => {
        setEdges(currentEdges => {
          setHistory(hist => [...hist, { nodes: JSON.parse(JSON.stringify(currentNodes)), edges: JSON.parse(JSON.stringify(currentEdges)) }])
          return next.edges
        })
        return next.nodes
      })
      setSelectedNode(null)
      return prev.slice(0, -1)
    })
  }

  // Adjust position based on sidebar state
  useEffect(() => {
    const adjustForSidebar = () => {
      if (!pipelineBuilderRef.current) return
      const sidebar = document.querySelector('.sidebar')
      if (sidebar) {
        const isOpen = sidebar.classList.contains('open')
        const sidebarWidth = isOpen ? 280 : 70
        pipelineBuilderRef.current.style.left = `${sidebarWidth}px`
        pipelineBuilderRef.current.style.width = `calc(100% - ${sidebarWidth}px)`
      } else {
        pipelineBuilderRef.current.style.left = '0'
        pipelineBuilderRef.current.style.width = '100%'
      }
    }

    adjustForSidebar()
    const observer = new MutationObserver(adjustForSidebar)
    const sidebar = document.querySelector('.sidebar')
    if (sidebar) {
      observer.observe(sidebar, { attributes: true, attributeFilter: ['class'] })
    }

    // Also check on window resize
    window.addEventListener('resize', adjustForSidebar)

    return () => {
      observer.disconnect()
      window.removeEventListener('resize', adjustForSidebar)
    }
  }, [])

  // Load connectors on mount and check URL for pipeline ID
  useEffect(() => {
    loadConnectors()
    // Check URL parameters for pipeline ID
    const urlParams = new URLSearchParams(window.location.search)
    const urlPipelineId = urlParams.get('pipeline')
    if (urlPipelineId) {
      loadPipeline(urlPipelineId)
    } else if (pipelineId) {
      loadPipeline(pipelineId)
    }
  }, [])

  const loadConnectors = async () => {
    try {
      const resp = await fetch(`${apiBase}/api/connectors`)
      if (resp.ok) {
        const data = await resp.json()
        setConnectors(data)
      }
    } catch (err) {
      console.error('Failed to load connectors:', err)
    }
  }

  const loadPipeline = async (id) => {
    try {
      const resp = await fetch(`${apiBase}/api/custom-pipelines/${id}`)
      if (resp.ok) {
        const data = await resp.json()
        setPipelineName(data.name || '')
        setPipelineDescription(data.description || '')
        setNodes(data.definition?.nodes || [])
        setEdges(data.definition?.edges || [])
        setCurrentPipelineId(id)
        // Load visualization config if it exists
        if (data.definition?.visualization_config) {
          setVisualizationConfig(data.definition.visualization_config)
        } else {
          setVisualizationConfig({
            selected_fields: [],
            order: [],
            visibility: {}
          })
        }
        // Update URL without reload
        const newUrl = new URL(window.location)
        newUrl.searchParams.set('pipeline', id)
        window.history.pushState({}, '', newUrl)
        // Set next node ID based on existing nodes
        if (data.definition?.nodes && data.definition.nodes.length > 0) {
          const maxId = Math.max(...data.definition.nodes.map(n => {
            const match = n.id.match(/node-(\d+)/)
            return match ? parseInt(match[1]) : 0
          }).concat([0]), 0)
          setNextNodeId(maxId + 1)
        }
        // Load fields if there's a source node
        const sourceNode = data.definition?.nodes?.find(n => n.type === 'source')
        if (sourceNode?.config?.connector_id) {
          loadFields(sourceNode.config.connector_id)
        }
        setShowPipelineList(false)
      } else {
        alert('Failed to load pipeline')
      }
    } catch (err) {
      console.error('Failed to load pipeline:', err)
      alert('Failed to load pipeline')
    }
  }

  const addNode = (type) => {
    pushHistory()
    const newNode = {
      id: `node-${nextNodeId}`,
      type: type,
      position: { x: Math.random() * 400 + 100, y: Math.random() * 300 + 100 },
      config: {}
    }
    setNodes([...nodes, newNode])
    setNextNodeId(nextNodeId + 1)
    setSelectedNode(newNode.id)
  }

  const deleteNode = (nodeId) => {
    pushHistory()
    setNodes(nodes.filter(n => n.id !== nodeId))
    setEdges(edges.filter(e => e.source !== nodeId && e.target !== nodeId))
    if (selectedNode === nodeId) {
      setSelectedNode(null)
    }
  }

  const updateNodeConfig = (nodeId, config) => {
    pushHistory()
    setNodes(nodes.map(n => 
      n.id === nodeId ? { ...n, config: { ...n.config, ...config } } : n
    ))
  }

  const updateNodePosition = (nodeId, position) => {
    // Don't push to history for position updates (too frequent)
    setNodes(nodes.map(n => 
      n.id === nodeId ? { ...n, position } : n
    ))
  }
  
  const updateNodePositionWithHistory = (nodeId, position) => {
    // This is called when drag ends - save to history
    pushHistory()
    setNodes(nodes.map(n => 
      n.id === nodeId ? { ...n, position } : n
    ))
  }

  const startConnection = (nodeId) => {
    setConnectingFrom(nodeId)
  }

  const completeConnection = (targetId) => {
    if (connectingFrom && connectingFrom !== targetId) {
      const edgeId = `edge-${connectingFrom}-${targetId}`
      if (!edges.find(e => e.id === edgeId)) {
        pushHistory()
        setEdges([...edges, {
          id: edgeId,
          source: connectingFrom,
          target: targetId
        }])
      }
    }
    setConnectingFrom(null)
  }
  
  // Update undo/redo refs when functions are defined
  useEffect(() => {
    undoRef.current = undo
    redoRef.current = redo
  }, [undo, redo])
  
  // Keyboard shortcuts for undo/redo
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Don't intercept if user is typing in an input field
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault()
        undoRef.current()
      } else if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault()
        redoRef.current()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const deleteEdge = (edgeId) => {
    pushHistory()
    setEdges(edges.filter(e => e.id !== edgeId))
  }

  const loadFields = async (connectorId) => {
    if (!connectorId) {
      setAvailableFields([])
      return
    }
    try {
      console.log('🔄 Loading fields for connector:', connectorId)
      setAvailableFields([]) // Clear previous fields while loading
      const url = `${apiBase}/api/connectors/${connectorId}/fields`
      console.log('📡 Fetching from URL:', url)
      
      const resp = await fetch(url)
      console.log('📥 Response status:', resp.status, resp.statusText)
      
      if (resp.ok) {
        const data = await resp.json()
        console.log('✅ Loaded fields response:', data)
        const fields = Array.isArray(data.fields) ? data.fields : []
        console.log(`✅ Found ${fields.length} fields:`, fields.map(f => f.name || f))
        
        // Ensure fields have the correct structure
        const normalizedFields = fields.map(f => {
          if (typeof f === 'string') {
            return { name: f, type: 'unknown' }
          }
          return {
            name: f.name || f.field || String(f),
            type: f.type || 'unknown',
            sample_value: f.sample_value
          }
        })
        
        setAvailableFields(normalizedFields)
        
        if (normalizedFields.length === 0) {
          console.warn('⚠️ No fields returned. Message:', data.message)
          // Show a more helpful message
          if (data.message) {
            console.warn('Backend message:', data.message)
          }
        }
      } else {
        const errorText = await resp.text()
        console.error('❌ Failed to load fields, status:', resp.status)
        console.error('Error response:', errorText)
        setAvailableFields([])
      }
    } catch (err) {
      console.error('❌ Exception loading fields:', err)
      setAvailableFields([])
    }
  }
  
  // Auto-load fields when source node connector changes
  useEffect(() => {
    const sourceNode = nodes.find(n => n.type === 'source')
    const sourceConnectorId = sourceNode?.config?.connector_id
    if (sourceConnectorId) {
      console.log('Auto-loading fields for source connector:', sourceConnectorId)
      loadFields(sourceConnectorId)
    } else {
      console.log('No source connector found, clearing fields')
      setAvailableFields([])
    }
  }, [nodes.find(n => n.type === 'source')?.config?.connector_id])

  const savePipeline = async () => {
    if (!pipelineName.trim()) {
      alert('Please enter a pipeline name')
      return
    }

    setIsSaving(true)
    try {
      const pipelineData = {
        pipeline_id: currentPipelineId || `pipeline-${Date.now()}`,
        name: pipelineName,
        description: pipelineDescription,
        nodes: nodes,
        edges: edges,
        visualization_config: visualizationConfig
      }

      const url = currentPipelineId 
        ? `${apiBase}/api/custom-pipelines/${currentPipelineId}`
        : `${apiBase}/api/custom-pipelines`
      
      const method = currentPipelineId ? 'PUT' : 'POST'

      const resp = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(pipelineData)
      })

      if (resp.ok) {
        alert('Pipeline saved successfully!')
        if (!currentPipelineId) {
          const result = await resp.json()
          // Reload with the new pipeline ID
          setCurrentPipelineId(result.pipeline_id)
          const newUrl = new URL(window.location)
          newUrl.searchParams.set('pipeline', result.pipeline_id)
          window.history.pushState({}, '', newUrl)
          loadPipeline(result.pipeline_id)
        }
      } else {
        throw new Error('Failed to save pipeline')
      }
    } catch (err) {
      console.error('Error saving pipeline:', err)
      alert('Failed to save pipeline')
    } finally {
      setIsSaving(false)
    }
  }

  const runPipeline = async () => {
    const targetId = currentPipelineId
    if (!targetId) {
      alert('Please save the pipeline first')
      return
    }

    setIsRunning(true)
    try {
      const resp = await fetch(`${apiBase}/api/custom-pipelines/${targetId}/run`, {
        method: 'POST'
      })

      if (resp.ok) {
        const result = await resp.json()
        setPipelineResults(result)
        setShowResults(true)
        setActiveTab('results')
        alert(`Pipeline executed! Processed ${result.records_processed || 0} records.`)
      } else {
        throw new Error('Failed to run pipeline')
      }
    } catch (err) {
      console.error('Error running pipeline:', err)
      alert('Failed to run pipeline')
    } finally {
      setIsRunning(false)
    }
  }

  const createNewPipeline = () => {
    pushHistory()
    setPipelineName('')
    setPipelineDescription('')
    setNodes([])
    setEdges([])
    setSelectedNode(null)
    setNextNodeId(1)
    setConnectingFrom(null)
    setShowPipelineList(false)
    setShowResults(false)
    setPipelineResults(null)
    setCurrentPipelineId(null)
    setVisualizationConfig({
      selected_fields: [],
      order: [],
      visibility: {}
    })
    window.history.replaceState({}, '', window.location.pathname)
  }

  // Convert nodes to SimpleFlow format
  const flowNodes = nodes.map(node => {
    const nodeType = NODE_TYPES[node.type] || NODE_TYPES.source
    const config = node.config || {}
    
    let label = nodeType.label
    if (node.type === 'source' && config.connector_id) {
      const connector = connectors.find(c => c.connector_id === config.connector_id)
      label = connector ? connector.name : config.connector_id
    } else if (node.type === 'field_selector' && config.selected_fields) {
      label = `${nodeType.label} (${config.selected_fields.length} fields)`
    } else if (node.type === 'filter' && config.filter) {
      label = `${nodeType.label}: ${config.filter.field} ${config.filter.operator} ${config.filter.value}`
    }

    return {
      id: node.id,
      data: { 
        label: (
          <div className="pipeline-builder-node" onClick={() => setSelectedNode(node.id)}>
            <div className="node-icon">{nodeType.icon}</div>
            <div className="node-label">{label}</div>
            {selectedNode === node.id && (
              <div className="node-selected-indicator">●</div>
            )}
          </div>
        )
      },
      position: node.position,
      style: {
        borderColor: hoveredNodeId === node.id ? '#3B82F6' : nodeType.color,
        borderWidth: selectedNode === node.id ? 3 : (hoveredNodeId === node.id ? 2 : 2),
        background: '#fff',
        padding: '8px 12px',
        borderRadius: '8px',
        minWidth: '120px',
        cursor: 'pointer',
        boxShadow: hoveredNodeId === node.id ? '0 0 0 2px rgba(59, 130, 246, 0.3)' : 'none',
        transition: 'all 0.2s'
      },
      className: selectedNode === node.id ? 'node-selected' : (hoveredNodeId === node.id ? 'node-hovered' : '')
    }
  })

  const flowEdges = edges.map(edge => ({
    ...edge,
    animated: true
  }))

  const selectedNodeData = nodes.find(n => n.id === selectedNode)

  return (
    <div className={`pipeline-builder ${sidebarOpen ? '' : 'sidebar-closed'}`} ref={pipelineBuilderRef}>
      <div className="pipeline-builder-header">
        <div className="pipeline-builder-header-left">
          <button 
            onClick={() => {
              if (onClose) {
                onClose()
              } else {
                window.history.back()
              }
            }} 
            className="pipeline-back-button"
            title="Go back"
          >
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 15l-5-5 5-5"/>
            </svg>
          </button>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1, minWidth: 0 }}>
            <h2 style={{ margin: 0, whiteSpace: 'nowrap', fontSize: '20px', fontWeight: 600 }}>Pipeline Builder</h2>
          </div>
        </div>
        <div className="pipeline-builder-actions">
          <button 
            onClick={undo}
            disabled={history.length === 0}
            className="pipeline-undo-btn"
            title="Undo (Ctrl+Z)"
            style={{
              padding: '8px 12px',
              border: 'none',
              borderRadius: '6px',
              background: history.length === 0 ? '#F3F4F6' : '#F3F4F6',
              color: history.length === 0 ? '#9CA3AF' : '#374151',
              cursor: history.length === 0 ? 'not-allowed' : 'pointer',
              fontSize: '13px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s'
            }}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 8h10M8 3l-5 5 5 5"/>
            </svg>
            Undo
          </button>
          <button 
            onClick={redo}
            disabled={future.length === 0}
            className="pipeline-redo-btn"
            title="Redo (Ctrl+Y)"
            style={{
              padding: '8px 12px',
              border: 'none',
              borderRadius: '6px',
              background: future.length === 0 ? '#F3F4F6' : '#F3F4F6',
              color: future.length === 0 ? '#9CA3AF' : '#374151',
              cursor: future.length === 0 ? 'not-allowed' : 'pointer',
              fontSize: '13px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s'
            }}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M13 8H3M8 3l5 5-5 5"/>
            </svg>
            Redo
          </button>
          <button 
            onClick={createNewPipeline} 
            className="pipeline-list-btn"
            title="Create a new pipeline"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 1v14M1 8h14"/>
            </svg>
            New
          </button>
          <button 
            onClick={() => setShowPipelineList(!showPipelineList)} 
            className="pipeline-list-btn"
            title="View saved pipelines"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M2 4h12M2 8h12M2 12h12"/>
            </svg>
            List
          </button>
          {connectingFrom && (
            <div style={{ 
              padding: '6px 12px', 
              background: '#EFF6FF', 
              color: '#3B82F6', 
              borderRadius: '6px', 
              fontSize: '12px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              Connecting from: {nodes.find(n => n.id === connectingFrom)?.type || connectingFrom}
              <button 
                onClick={() => setConnectingFrom(null)}
                style={{ 
                  background: 'none', 
                  border: 'none', 
                  color: '#3B82F6', 
                  cursor: 'pointer',
                  fontSize: '16px',
                  padding: '0',
                  lineHeight: '1'
                }}
                title="Cancel connection"
              >
                ✕
              </button>
            </div>
          )}
          <button onClick={savePipeline} disabled={isSaving} className="pipeline-save-btn">
            {isSaving ? 'Saving...' : 'Save Pipeline'}
          </button>
          <VisualizationParametersPanel
            nodes={nodes}
            edges={edges}
            availableFields={availableFields}
            pipelineResults={pipelineResults}
            visualizationConfig={visualizationConfig}
            onConfigChange={setVisualizationConfig}
            selectedNode={hoveredNodeId}
            onNodeHover={setHoveredNodeId}
          />
          <button 
            onClick={runPipeline} 
            disabled={isRunning || !currentPipelineId} 
            className="pipeline-run-btn"
            title={currentPipelineId ? 'Run pipeline' : 'Save first to enable run'}
          >
            {isRunning ? 'Running...' : 'Run Pipeline'}
          </button>
          {currentPipelineId && pipelineResults && (
            <div className="pipeline-view-tabs" role="tablist">
              <button
                className={`tab ${activeTab === 'canvas' ? 'active' : ''}`}
                onClick={() => setActiveTab('canvas')}
                role="tab"
                aria-selected={activeTab === 'canvas'}
              >
                Canvas
              </button>
              <button
                className={`tab ${activeTab === 'results' ? 'active' : ''}`}
                onClick={() => setActiveTab('results')}
                role="tab"
                aria-selected={activeTab === 'results'}
              >
                Results
              </button>
              <button
                className={`tab ${activeTab === 'visualization' ? 'active' : ''}`}
                onClick={() => setActiveTab('visualization')}
                role="tab"
                aria-selected={activeTab === 'visualization'}
              >
                📊 Visualization
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="pipeline-builder-body" style={{ marginBottom: activeTab === 'results' ? '0' : '0', transition: 'margin-bottom 0.3s ease' }}>
        <div className={`pipeline-builder-sidebar ${sidebarOpen ? '' : 'collapsed'}`}>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
            <button
              onClick={() => setSidebarOpen(false)}
              className="sidebar-close-btn"
              title="Close sidebar"
              style={{ background: 'none', border: 'none', fontSize: '24px', color: '#9ca3af', cursor: 'pointer', padding: '0 4px', lineHeight: '1' }}
            >
              ×
            </button>
          </div>
          <div className="sidebar-section">
            <h3>Pipeline Details</h3>
            <input
              type="text"
              placeholder="Pipeline Name"
              value={pipelineName}
              onChange={(e) => setPipelineName(e.target.value)}
              className="pipeline-name-input"
              style={{ width: '100%', marginBottom: '8px' }}
            />
            <textarea
              placeholder="Description (optional)"
              value={pipelineDescription}
              onChange={(e) => setPipelineDescription(e.target.value)}
              className="pipeline-description-input"
              rows="2"
              style={{ width: '100%', resize: 'vertical' }}
            />
          </div>
          <div className="sidebar-section">
            <h3>Add Nodes</h3>
            {Object.entries(NODE_TYPES).map(([type, info]) => (
              <button
                key={type}
                className="add-node-btn"
                onClick={() => addNode(type)}
              >
                {info.icon} {info.label}
              </button>
            ))}
            <div style={{ 
              marginTop: '12px', 
              padding: '10px', 
              background: '#F0F9FF', 
              borderRadius: '6px', 
              fontSize: '11px',
              color: '#0369A1',
              lineHeight: '1.5'
            }}>
              <strong>💡 How to Connect:</strong><br/>
              1. Click a node to select it<br/>
              2. Click another node to connect<br/>
              3. Arrows appear automatically
            </div>
          </div>
          
          {showPipelineList && (
            <div className="sidebar-section">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <h3>Saved Pipelines</h3>
                <button
                  onClick={() => setShowPipelineList(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#6B7280',
                    cursor: 'pointer',
                    fontSize: '18px',
                    padding: '0 4px'
                  }}
                >
                  ×
                </button>
              </div>
              <SavedPipelinesList 
                apiBase={apiBase}
                onLoadPipeline={loadPipeline}
              />
            </div>
          )}

        </div>

        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
          {activeTab === 'canvas' && (
            <div className="pipeline-builder-canvas-wrapper">
              <div className="pipeline-builder-canvas" ref={containerRef}>
                <EditableFlow 
                  nodes={flowNodes} 
                  edges={flowEdges}
                  onNodeDrag={updateNodePosition}
                  onNodeClick={setSelectedNode}
                  onStartConnection={startConnection}
                  onCompleteConnection={completeConnection}
                  connectingFrom={connectingFrom}
                />
              </div>
            </div>
          )}

          {activeTab === 'results' && pipelineResults && (
            <div className="pipeline-results-inline-wrapper">
              <PipelineResultsPanel 
                results={pipelineResults}
                onClose={() => setActiveTab('canvas')}
                inline={true}
              />
            </div>
          )}

          {activeTab === 'visualization' && pipelineResults && (
            <div className="pipeline-results-inline-wrapper">
              <PipelineVisualization
                pipelineResults={pipelineResults}
                visualizationConfig={visualizationConfig}
                availableFields={availableFields}
              />
            </div>
          )}
        </div>

        {selectedNodeData && (
          <div className="node-config-side-panel">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: '12px', borderBottom: '1px solid #e5e7eb' }}>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#1f2937' }}>⚙️ {NODE_TYPES[selectedNodeData.type]?.label}</span>
              <button
                onClick={() => setSelectedNode(null)}
                className="node-config-close-btn"
                title="Close configuration"
              >
                ✕
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <NodeConfigPanel
                node={selectedNodeData}
                connectors={connectors}
                availableFields={availableFields}
                onConfigChange={(config) => updateNodeConfig(selectedNode, config)}
                onLoadFields={loadFields}
                allNodes={nodes}
              />
            </div>
            <button
              className="node-config-delete-btn"
              onClick={() => deleteNode(selectedNode)}
              title="Delete this node"
              style={{ marginTop: 'auto' }}
            >
              Delete Node
            </button>
          </div>
        )}
      </div>
      
    </div>
  )
}

function NodeConfigPanel({ node, connectors, availableFields, onConfigChange, onLoadFields, allNodes = [] }) {
  const config = node.config || {}
  
  // Find source node to get available fields for filter/transform nodes
  const sourceNode = allNodes.find(n => n.type === 'source')
  const sourceConnectorId = sourceNode?.config?.connector_id
  
  // Show message if no fields available
  const hasFields = availableFields.length > 0
  
  // Force reload fields if we have a source connector but no fields
  useEffect(() => {
    if (sourceConnectorId && availableFields.length === 0 && (node.type === 'filter' || node.type === 'field_selector')) {
      console.log('NodeConfigPanel: Triggering field load for', sourceConnectorId)
      onLoadFields(sourceConnectorId)
    }
  }, [sourceConnectorId, node.type, availableFields.length])

  if (node.type === 'source') {
    return (
      <div className="node-config-panel">
        <label>Connector</label>
        <select
          value={config.connector_id || ''}
          onChange={(e) => {
            onConfigChange({ connector_id: e.target.value })
            if (e.target.value) {
              onLoadFields(e.target.value)
            }
          }}
        >
          <option value="">Select connector...</option>
          {connectors.map(c => (
            <option key={c.connector_id} value={c.connector_id}>
              {c.name || c.connector_id}
            </option>
          ))}
        </select>
        <label>Limit</label>
        <input
          type="number"
          value={config.limit || 100}
          onChange={(e) => onConfigChange({ limit: parseInt(e.target.value) || 100 })}
        />
      </div>
    )
  }

  if (node.type === 'field_selector') {
    const selectedFields = config.selected_fields || []
    
    const toggleField = (fieldName) => {
      if (selectedFields.includes(fieldName)) {
        onConfigChange({ selected_fields: selectedFields.filter(f => f !== fieldName) })
      } else {
        onConfigChange({ selected_fields: [...selectedFields, fieldName] })
      }
    }
    
    return (
      <div className="node-config-panel">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
          <label style={{ fontSize: '10px', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Select Fields</label>
          {!hasFields ? (
            <div className="field-selector-empty" style={{ padding: '12px', fontSize: '12px', color: '#6B7280', background: '#f9fafb', borderRadius: '5px', textAlign: 'center' }}>
              {sourceConnectorId ? (
                <>Loading fields...</>
              ) : (
                <>Configure Source node</>
              )}
            </div>
          ) : (
            <div style={{
              border: '1px solid #e5e7eb',
              borderRadius: '5px',
              background: 'white',
              maxHeight: '150px',
              overflowY: 'auto',
              padding: '6px'
            }}>
              {availableFields.map(field => (
                <label key={field.name} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '6px 8px',
                  cursor: 'pointer',
                  borderRadius: '4px',
                  transition: 'background 0.2s'
                }} onMouseEnter={(e) => e.currentTarget.style.background = '#f3f4f6'} onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                  <input
                    type="checkbox"
                    checked={selectedFields.includes(field.name)}
                    onChange={() => toggleField(field.name)}
                    style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                  />
                  <span style={{ fontSize: '12px', color: '#374151', flex: 1 }}>
                    {field.name}
                  </span>
                  <span style={{ fontSize: '10px', color: '#9ca3af' }}>
                    {field.type}
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>
        {selectedFields.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '10px', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Selected ({selectedFields.length})</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {selectedFields.map(field => (
                <span key={field} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 8px', background: '#EDE9FE', color: '#6D28D9', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>
                  {field}
                  <button
                    type="button"
                    onClick={() => {
                      onConfigChange({ selected_fields: selectedFields.filter(f => f !== field) })
                    }}
                    style={{ background: 'none', border: 'none', color: '#6D28D9', cursor: 'pointer', fontSize: '14px', lineHeight: '1', padding: '0' }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  if (node.type === 'filter') {
    // Get available fields - use current availableFields
    const filterFields = availableFields.length > 0 ? availableFields.map(f => f.name) : []
    
    return (
      <div className="node-config-panel">
        <label>Field</label>
        {!hasFields ? (
          <div className="field-selector-empty" style={{ padding: '8px', fontSize: '12px' }}>
            {sourceConnectorId ? (
              <>
                <p style={{ marginBottom: '8px' }}>⏳ Loading fields from source connector...</p>
                <p style={{ fontSize: '11px', marginTop: '4px', color: '#6B7280' }}>
                  <strong>Connector:</strong> {sourceConnectorId}
                </p>
                <p style={{ fontSize: '11px', marginTop: '8px', color: '#9CA3AF', fontStyle: 'italic' }}>
                  💡 Tip: Make sure the connector has been run at least once and has data in the database.
                </p>
                <button
                  type="button"
                  onClick={() => onLoadFields(sourceConnectorId)}
                  style={{
                    marginTop: '12px',
                    padding: '6px 12px',
                    fontSize: '12px',
                    background: '#3B82F6',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  🔄 Retry Loading Fields
                </button>
              </>
            ) : (
              'Configure Source node first to see available fields'
            )}
          </div>
        ) : filterFields.length > 0 ? (
          <select
            value={config.filter?.field || ''}
            onChange={(e) => onConfigChange({
              filter: { ...config.filter, field: e.target.value }
            })}
          >
            <option value="">Select field...</option>
            {filterFields.map(field => (
              <option key={field} value={field}>{field}</option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            placeholder="field.name (e.g., price, symbol)"
            value={config.filter?.field || ''}
            onChange={(e) => onConfigChange({
              filter: { ...config.filter, field: e.target.value }
            })}
          />
        )}
        <label>Operator</label>
        <select
          value={config.filter?.operator || 'equals'}
          onChange={(e) => onConfigChange({
            filter: { ...config.filter, operator: e.target.value }
          })}
        >
          <option value="equals">Equals (=)</option>
          <option value="greater_than">Greater Than (&gt;)</option>
          <option value="less_than">Less Than (&lt;)</option>
          <option value="contains">Contains</option>
          <option value="not_equals">Not Equals (!=)</option>
        </select>
        <label>Value</label>
        <input
          type="text"
          placeholder="filter value"
          value={config.filter?.value || ''}
          onChange={(e) => onConfigChange({
            filter: { ...config.filter, value: e.target.value }
          })}
        />
      </div>
    )
  }

  if (node.type === 'transform') {
    const transformations = config.transformations || []
    const transformFields = availableFields.length > 0 ? availableFields.map(f => f.name) : []
    
    const addTransformation = () => {
      onConfigChange({
        transformations: [...transformations, {
          type: 'rename',
          source_field: '',
          target_field: '',
          expression: ''
        }]
      })
    }
    
    const updateTransformation = (index, updates) => {
      const updated = [...transformations]
      updated[index] = { ...updated[index], ...updates }
      onConfigChange({ transformations: updated })
    }
    
    const removeTransformation = (index) => {
      onConfigChange({
        transformations: transformations.filter((_, i) => i !== index)
      })
    }
    
    return (
      <div className="node-config-panel">
        <label>Transformations</label>
        {!hasFields ? (
          <div className="field-selector-empty" style={{ padding: '8px', fontSize: '12px' }}>
            {sourceConnectorId ? (
              <>
                <p style={{ marginBottom: '8px' }}>⏳ Loading fields from source connector...</p>
                <button
                  type="button"
                  onClick={() => onLoadFields(sourceConnectorId)}
                  style={{
                    marginTop: '8px',
                    padding: '6px 12px',
                    fontSize: '12px',
                    background: '#3B82F6',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  🔄 Retry Loading Fields
                </button>
              </>
            ) : (
              'Configure Source node first to see available fields'
            )}
          </div>
        ) : (
          <>
            <div style={{ marginBottom: '12px' }}>
              <button
                type="button"
                onClick={addTransformation}
                style={{
                  padding: '6px 12px',
                  fontSize: '12px',
                  background: '#78176b',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  width: '100%'
                }}
              >
                + Add Transformation
              </button>
            </div>
            {transformations.map((transform, index) => (
              <div key={index} style={{ 
                marginBottom: '12px', 
                padding: '12px', 
                background: '#F9FAFB', 
                border: '1px solid #E5E7EB',
                borderRadius: '6px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <strong style={{ fontSize: '12px' }}>Transformation {index + 1}</strong>
                  <button
                    type="button"
                    onClick={() => removeTransformation(index)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#EF4444',
                      cursor: 'pointer',
                      fontSize: '16px',
                      padding: '0 4px'
                    }}
                  >
                    ×
                  </button>
                </div>
                <label style={{ fontSize: '11px', display: 'block', marginBottom: '4px' }}>Type</label>
                <select
                  value={transform.type || 'rename'}
                  onChange={(e) => updateTransformation(index, { type: e.target.value })}
                  style={{ width: '100%', padding: '6px', fontSize: '12px', marginBottom: '8px', borderRadius: '4px', border: '1px solid #D1D5DB' }}
                >
                  <option value="rename">Rename Field</option>
                  <option value="calculate">Calculate</option>
                  <option value="format">Format</option>
                </select>
                <label style={{ fontSize: '11px', display: 'block', marginBottom: '4px' }}>Source Field</label>
                <select
                  value={transform.source_field || ''}
                  onChange={(e) => updateTransformation(index, { source_field: e.target.value })}
                  style={{ width: '100%', padding: '6px', fontSize: '12px', marginBottom: '8px', borderRadius: '4px', border: '1px solid #D1D5DB' }}
                >
                  <option value="">Select field...</option>
                  {transformFields.map(field => (
                    <option key={field} value={field}>{field}</option>
                  ))}
                </select>
                {transform.type === 'rename' && (
                  <>
                    <label style={{ fontSize: '11px', display: 'block', marginBottom: '4px' }}>Target Field Name</label>
                    <input
                      type="text"
                      value={transform.target_field || ''}
                      onChange={(e) => updateTransformation(index, { target_field: e.target.value })}
                      placeholder="New field name"
                      style={{ width: '100%', padding: '6px', fontSize: '12px', borderRadius: '4px', border: '1px solid #D1D5DB' }}
                    />
                  </>
                )}
                {(transform.type === 'calculate' || transform.type === 'format') && (
                  <>
                    <label style={{ fontSize: '11px', display: 'block', marginBottom: '4px' }}>Expression/Format</label>
                    <input
                      type="text"
                      value={transform.expression || ''}
                      onChange={(e) => updateTransformation(index, { expression: e.target.value })}
                      placeholder={transform.type === 'calculate' ? 'e.g., value * 2' : 'e.g., YYYY-MM-DD'}
                      style={{ width: '100%', padding: '6px', fontSize: '12px', borderRadius: '4px', border: '1px solid #D1D5DB' }}
                    />
                  </>
                )}
              </div>
            ))}
            {transformations.length === 0 && (
              <p className="config-hint" style={{ fontSize: '12px', color: '#6B7280', fontStyle: 'italic', marginTop: '8px' }}>
                Click "Add Transformation" to configure field transformations
              </p>
            )}
          </>
        )}
      </div>
    )
  }

  if (node.type === 'destination') {
    return <DestinationNodeConfig node={node} config={config} onConfigChange={onConfigChange} />
  }

  return <div>No configuration available</div>
}

// Editable Flow Component with Draggable Nodes
function EditableFlow({ nodes, edges, onNodeDrag, onNodeClick, onStartConnection, onCompleteConnection, connectingFrom }) {
  const containerRef = useRef(null)
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 })
  const [isDragging, setIsDragging] = useState(false)
  const [draggedNode, setDraggedNode] = useState(null)
  const [lastMousePos, setLastMousePos] = useState({ x: 0, y: 0 })
  const [nodeOffset, setNodeOffset] = useState({ x: 0, y: 0 })

  const handleNodeMouseDown = (e, nodeId) => {
    e.stopPropagation()
    const node = nodes.find(n => n.id === nodeId)
    if (!node) return
    
    const rect = e.currentTarget.getBoundingClientRect()
    
    setDraggedNode(nodeId)
    setNodeOffset({
      x: e.clientX - rect.left - (rect.width / 2),
      y: e.clientY - rect.top - (rect.height / 2)
    })
    setLastMousePos({ x: e.clientX, y: e.clientY })
    setIsDragging(true)
  }

  const handleMouseMove = (e) => {
    if (!isDragging) return
    
    if (draggedNode) {
      // Dragging a node
      const containerRect = containerRef.current.getBoundingClientRect()
      const scale = transform.scale
      const x = (e.clientX - containerRect.left - transform.x) / scale - nodeOffset.x
      const y = (e.clientY - containerRect.top - transform.y) / scale - nodeOffset.y
      
      onNodeDrag(draggedNode, { x: Math.max(0, x), y: Math.max(0, y) })
    } else {
      // Panning the canvas
      const dx = e.clientX - lastMousePos.x
      const dy = e.clientY - lastMousePos.y
      setTransform(prev => ({ ...prev, x: prev.x + dx, y: prev.y + dy }))
    }
    
    setLastMousePos({ x: e.clientX, y: e.clientY })
  }

  const handleMouseUp = () => {
    setIsDragging(false)
    setDraggedNode(null)
  }

  const handleCanvasMouseDown = (e) => {
    if (e.target === containerRef.current || e.target.closest('.simple-flow-canvas')) {
      setIsDragging(true)
      setLastMousePos({ x: e.clientX, y: e.clientY })
    }
  }

  const getNodeCenter = (nodeId) => {
    const node = nodes.find(n => n.id === nodeId)
    if (!node) return { x: 0, y: 0 }
    const width = node.style?.width || 160
    const height = 60
    return { x: node.position.x, y: node.position.y, w: width, h: height }
  }

  return (
    <div 
      className="simple-flow-container" 
      ref={containerRef}
      onMouseDown={handleCanvasMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <div 
        className="simple-flow-canvas" 
        style={{ 
          transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})` 
        }}
      >
        <svg className="simple-flow-edges" style={{ overflow: 'visible' }}>
          <defs>
            <marker
              id="edge-arrow"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#b1b1b7" />
            </marker>
            <marker
              id="edge-arrow-animated"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#2F80ED" />
            </marker>
          </defs>
          {edges.map(edge => {
            const source = getNodeCenter(edge.source)
            const target = getNodeCenter(edge.target)
            
            const sx = source.x + source.w
            const sy = source.y + source.h / 2
            const tx = target.x
            const ty = target.y + target.h / 2
            
            const dist = Math.abs(tx - sx)
            const cp1x = sx + dist / 2
            const cp1y = sy
            const cp2x = tx - dist / 2
            const cp2y = ty
            
            const path = `M ${sx} ${sy} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${tx} ${ty}`
            
            return (
              <g key={edge.id}>
                <path 
                  d={path} 
                  className="flow-edge-path" 
                  markerEnd="url(#edge-arrow)"
                />
                {edge.animated && (
                  <path 
                    d={path} 
                    className="flow-edge-path-animated" 
                    markerEnd="url(#edge-arrow-animated)"
                  />
                )}
              </g>
            )
          })}
        </svg>
        {nodes.map(node => (
          <div 
            key={node.id} 
            className={`flow-node ${node.className || ''} ${draggedNode === node.id ? 'dragging' : ''}`}
            style={{ 
              left: node.position.x, 
              top: node.position.y, 
              ...node.style,
              cursor: 'grab',
              borderColor: connectingFrom === node.id ? '#3B82F6' : node.style.borderColor,
              borderWidth: connectingFrom === node.id ? 3 : node.style.borderWidth,
              boxShadow: connectingFrom === node.id ? '0 0 0 3px rgba(59, 130, 246, 0.3)' : 'none'
            }}
            onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
            onClick={(e) => {
              e.stopPropagation()
              // Handle node connections
              if (connectingFrom && connectingFrom !== node.id && onCompleteConnection) {
                onCompleteConnection(node.id)
              } else if (onStartConnection && !connectingFrom) {
                onStartConnection(node.id)
              }
              onNodeClick(node.id)
            }}
          >
            {node.data.label}
          </div>
        ))}
      </div>
    </div>
  )
}

// Destination Node Configuration Component
function DestinationNodeConfig({ node, config, onConfigChange }) {
  const [isDragging, setIsDragging] = useState(false)
  const [isLoadingFile, setIsLoadingFile] = useState(false)
  const fileInputRef = useRef(null)
  
  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }
  
  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }
  
  const handleDrop = async (e) => {
    e.preventDefault()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      await handleFileLoad(files[0])
    }
  }
  
  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0]
    if (file) {
      await handleFileLoad(file)
    }
  }
  
  const handleFileLoad = async (file) => {
    setIsLoadingFile(true)
    try {
      const text = await file.text()
      let data
      if (file.name.endsWith('.json')) {
        data = JSON.parse(text)
      } else if (file.name.endsWith('.csv')) {
        // Simple CSV parsing
        const lines = text.split('\n')
        const headers = lines[0].split(',')
        data = lines.slice(1).map(line => {
          const values = line.split(',')
          const obj = {}
          headers.forEach((header, i) => {
            obj[header.trim()] = values[i]?.trim() || ''
          })
          return obj
        }).filter(obj => Object.keys(obj).length > 0)
      }
      
      onConfigChange({
        destination: {
          ...config.destination,
          type: 'file',
          file_name: file.name,
          file_type: file.type,
          file_size: file.size,
          loaded_data: data
        }
      })
    } catch (err) {
      console.error('Error loading file:', err)
      alert('Failed to load file. Please check the file format.')
    } finally {
      setIsLoadingFile(false)
    }
  }
  
  const destinationType = config.destination?.type || 'database'
  
  return (
    <div className="destination-node-config">
      <div>
        <label style={{ fontSize: '10px', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Destination Type</label>
        <select
          value={destinationType}
          onChange={(e) => onConfigChange({
            destination: { ...config.destination, type: e.target.value }
          })}
          style={{ padding: '7px 10px', borderRadius: '5px', border: '1px solid #e5e7eb', fontSize: '12px', width: '100%' }}
        >
          <option value="database">Database</option>
          <option value="file">File (CSV/JSON)</option>
          <option value="load">Load from File</option>
        </select>
      </div>
      
      {destinationType === 'database' ? (
        <div>
          <label style={{ fontSize: '10px', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Connector ID</label>
          <input
            type="text"
            placeholder="custom_pipeline"
            value={config.connector_id || ''}
            onChange={(e) => onConfigChange({ connector_id: e.target.value })}
            style={{ padding: '7px 10px', borderRadius: '5px', border: '1px solid #e5e7eb', fontSize: '12px', width: '100%' }}
          />
        </div>
      ) : destinationType === 'load' ? (
        <div style={{ width: '100%' }}>
          <label style={{ fontSize: '10px', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Load Data from File</label>
          <div
            className={`file-drop-zone ${isDragging ? 'dragging' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: `2px dashed ${isDragging ? '#3B82F6' : '#d1d5db'}`,
              borderRadius: '6px',
              padding: '20px',
              textAlign: 'center',
              cursor: 'pointer',
              background: isDragging ? '#EFF6FF' : '#F9FAFB',
              transition: 'all 0.2s',
              minHeight: '80px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.json"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            {isLoadingFile ? (
              <div>
                <p style={{ margin: 0, color: '#3B82F6' }}>Loading file...</p>
              </div>
            ) : config.destination?.file_name ? (
              <div>
                <p style={{ margin: 0, color: '#10B981', fontWeight: 500 }}>
                  ✓ {config.destination.file_name}
                </p>
                <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#6B7280' }}>
                  {config.destination.loaded_data ? `${Array.isArray(config.destination.loaded_data) ? config.destination.loaded_data.length : 1} records loaded` : 'Click to change file'}
                </p>
              </div>
            ) : (
              <div>
                <p style={{ margin: 0, color: '#6B7280' }}>
                  📁 Drag & drop a file here or click to select
                </p>
                <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#9CA3AF' }}>
                  Supports CSV and JSON files
                </p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', width: '100%' }}>
          <label style={{ fontSize: '10px', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.3px' }}>File Export</label>
          <div
            className={`file-drop-zone ${isDragging ? 'dragging' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: `2px dashed ${isDragging ? '#3B82F6' : '#d1d5db'}`,
              borderRadius: '6px',
              padding: '20px',
              textAlign: 'center',
              cursor: 'pointer',
              background: isDragging ? '#EFF6FF' : '#F9FAFB',
              transition: 'all 0.2s'
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.json"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            {config.destination?.file_name ? (
              <div>
                <p style={{ margin: 0, color: '#10B981', fontWeight: 500 }}>
                  ✓ {config.destination.file_name}
                </p>
                <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#6B7280' }}>
                  Click to change file
                </p>
              </div>
            ) : (
              <div>
                <p style={{ margin: 0, color: '#6B7280' }}>
                  📁 Drag & drop a file here or click to select
                </p>
                <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#9CA3AF' }}>
                  Supports CSV and JSON files
                </p>
              </div>
            )}
          </div>
          <div>
            <label style={{ fontSize: '10px', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.3px' }}>File Format</label>
            <select
              value={config.destination?.file_format || 'csv'}
              onChange={(e) => onConfigChange({
                destination: { ...config.destination, file_format: e.target.value }
              })}
              style={{ padding: '7px 10px', borderRadius: '5px', border: '1px solid #e5e7eb', fontSize: '12px', width: '100%' }}
            >
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </select>
          </div>
        </div>
      )}
    </div>
  )
}

// Saved Pipelines List Component
function SavedPipelinesList({ apiBase, onLoadPipeline }) {
  const [pipelines, setPipelines] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadPipelines()
  }, [])

  const loadPipelines = async () => {
    try {
      setLoading(true)
      const resp = await fetch(`${apiBase}/api/custom-pipelines`)
      if (resp.ok) {
        const data = await resp.json()
        // Backend returns array directly or wrapped in pipelines key
        setPipelines(Array.isArray(data) ? data : (data.pipelines || []))
      } else {
        setError('Failed to load pipelines')
      }
    } catch (err) {
      console.error('Error loading pipelines:', err)
      setError('Failed to load pipelines')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div style={{ padding: '8px', fontSize: '12px', color: '#6B7280' }}>Loading...</div>
  }

  if (error) {
    return <div style={{ padding: '8px', fontSize: '12px', color: '#EF4444' }}>{error}</div>
  }

  if (pipelines.length === 0) {
    return (
      <div style={{ padding: '8px', fontSize: '12px', color: '#6B7280' }}>
        No saved pipelines yet
      </div>
    )
  }

  return (
    <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
      {pipelines.map(pipeline => (
        <div
          key={pipeline.pipeline_id}
          onClick={() => onLoadPipeline(pipeline.pipeline_id)}
          style={{
            padding: '8px 12px',
            marginBottom: '4px',
            background: '#F9FAFB',
            border: '1px solid #E5E7EB',
            borderRadius: '4px',
            cursor: 'pointer',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#F3F4F6'
            e.currentTarget.style.borderColor = '#D1D5DB'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = '#F9FAFB'
            e.currentTarget.style.borderColor = '#E5E7EB'
          }}
        >
          <div style={{ fontWeight: 500, fontSize: '13px', color: '#111827' }}>
            {pipeline.name}
          </div>
          {pipeline.description && (
            <div style={{ fontSize: '11px', color: '#6B7280', marginTop: '2px' }}>
              {pipeline.description.substring(0, 40)}...
            </div>
          )}
          <div style={{ fontSize: '10px', color: '#9CA3AF', marginTop: '4px' }}>
            {pipeline.run_count || 0} runs • {pipeline.status || 'active'}
          </div>
        </div>
      ))}
    </div>
  )
}

// Pipeline Results Panel Component
function PipelineResultsPanel({ results, onClose, inline = false }) {
  const stepResults = results.step_results || []
  const finalData = results.final_data || []
  const panelRef = useRef(null)
  
  // Find selected fields from field_selector step
  const fieldSelectorStep = stepResults.find(step => step.node_type === 'field_selector')
  const selectedFields = fieldSelectorStep?.selected_fields || null
  
  // If not inline, adjust position based on sidebar state (overlay behavior)
  useEffect(() => {
    if (inline) return
    const adjustForSidebar = () => {
      if (!panelRef.current) return
      const sidebar = document.querySelector('.sidebar')
      if (sidebar) {
        const isOpen = sidebar.classList.contains('open')
        const sidebarWidth = isOpen ? 280 : 70
        panelRef.current.style.left = `${sidebarWidth}px`
        panelRef.current.style.width = `calc(100% - ${sidebarWidth}px)`
      } else {
        panelRef.current.style.left = '0'
        panelRef.current.style.width = '100%'
      }
    }

    adjustForSidebar()
    const observer = new MutationObserver(adjustForSidebar)
    const sidebar = document.querySelector('.sidebar')
    if (sidebar) {
      observer.observe(sidebar, { attributes: true, attributeFilter: ['class'] })
    }

    window.addEventListener('resize', adjustForSidebar)

    return () => {
      observer.disconnect()
      window.removeEventListener('resize', adjustForSidebar)
    }
  }, [inline])
  
  return (
    <div className={inline ? 'pipeline-results-inline' : 'pipeline-results-panel'} ref={panelRef}>
      <div className="pipeline-results-header">
        <h3>Execution Results</h3>
        <button 
          onClick={onClose} 
          style={{
            background: 'none',
            border: 'none',
            fontSize: '18px',
            cursor: 'pointer',
            color: '#6B7280',
            padding: '0 8px',
            lineHeight: '1',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '24px',
            height: '24px',
            borderRadius: '4px',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#F3F4F6'
            e.currentTarget.style.color = '#111827'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'none'
            e.currentTarget.style.color = '#6B7280'
          }}
        >
          ×
        </button>
      </div>
      
      <div className="pipeline-results-summary">
        <div className="result-stat">
          <div className="result-stat-label">Processed</div>
          <div className="result-stat-value">{results.records_processed || 0}</div>
        </div>
        <div className="result-stat">
          <div className="result-stat-label">Records Saved</div>
          <div className="result-stat-value">{results.records_saved || 0}</div>
        </div>
        <div className="result-stat">
          <div className="result-stat-label">Execution Time</div>
          <div className="result-stat-value">{results.execution_time_ms ? `${(results.execution_time_ms / 1000).toFixed(2)}s` : 'N/A'}</div>
        </div>
      </div>
      
      <div className="pipeline-results-steps">
        <h4>Step Results</h4>
        {stepResults.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center', color: '#6B7280', fontSize: '12px' }}>
            No step results available
          </div>
        ) : (
          stepResults.map((step, index) => (
            <div key={index} className="result-step">
              <div className="result-step-header">
                <span className="result-step-number">{index + 1}</span>
                <span className="result-step-name">{step.node_name || step.node_type}</span>
                <span className="result-step-count">{step.records_count || 0} records</span>
              </div>
              {step.error ? (
                <div className="result-step-error" style={{ 
                  fontSize: '11px', 
                  padding: '6px 8px', 
                  marginTop: '8px',
                  borderRadius: '4px'
                }}>
                  Error: {step.error}
                </div>
              ) : (
                <>
                  {step.records_before !== undefined && (
                    <div className="result-step-info" style={{ fontSize: '11px', marginTop: '4px' }}>
                      Before: {step.records_before} → After: {step.records_after}
                    </div>
                  )}
                  {step.sample_data && step.sample_data.length > 0 && (() => {
                    // The backend already filters data correctly after field_selector
                    // So we just display whatever keys are in the data
                    // For source step (before field_selector), show all fields
                    // For steps after field_selector, data already contains only selected fields
                    const firstRecord = step.sample_data[0]
                    if (!firstRecord || typeof firstRecord !== 'object') {
                      return null
                    }
                    
                    const fieldsToShow = Object.keys(firstRecord)
                    const fieldSelectorIndex = stepResults.findIndex(s => s.node_type === 'field_selector')
                    const isAfterFieldSelector = selectedFields && selectedFields.length > 0 && 
                                                 fieldSelectorIndex >= 0 && fieldSelectorIndex < index
                    
                    return (
                      <div className="result-step-data" style={{ marginTop: '8px' }}>
                        <div style={{ fontSize: '11px', fontWeight: 500, color: '#374151', marginBottom: '6px' }}>
                          Table Data:
                          {isAfterFieldSelector && selectedFields && (
                            <span style={{ marginLeft: '8px', color: '#6B7280', fontWeight: 400 }}>
                              ({selectedFields.length} selected {selectedFields.length === 1 ? 'field' : 'fields'})
                            </span>
                          )}
                        </div>
                        {fieldsToShow.length > 0 ? (
                          <div className="data-table-container">
                            <table className="data-table">
                              <thead>
                                <tr>
                                  {fieldsToShow.map(key => (
                                    <th key={key}>{key}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {step.sample_data.slice(0, 5).map((row, idx) => (
                                  <tr key={idx}>
                                    {fieldsToShow.map(field => {
                                      const value = row[field]
                                      return (
                                        <td key={field} title={value !== undefined && value !== null ? String(value) : ''}>
                                          {value === undefined || value === null ? '-' : 
                                           typeof value === 'object' ? JSON.stringify(value).substring(0, 40) : 
                                           String(value).substring(0, 40)}
                                        </td>
                                      )
                                    })}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <div style={{ padding: '12px', color: '#6B7280', fontSize: '11px', fontStyle: 'italic' }}>
                            No fields to display
                          </div>
                        )}
                      </div>
                    )
                  })()}
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default PipelineBuilder

