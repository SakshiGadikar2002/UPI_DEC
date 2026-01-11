import { useState, useEffect, useMemo, useRef } from 'react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
  useDraggable
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import './VisualizationParametersPanel.css'

function VisualizationParametersPanel({
  nodes = [],
  edges = [],
  availableFields = [],
  pipelineResults = null,
  visualizationConfig = null,
  onConfigChange = () => {},
  selectedNode,
  onNodeHover = () => {}
}) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [activeId, setActiveId] = useState(null)
  const dragStartRef = useRef(null)

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // Require 8px of movement before drag starts
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  )

  // Extract available output parameters from pipeline
  const availableParameters = useMemo(() => {
    const params = new Map()

    // Extract from availableFields (source node)
    if (availableFields && availableFields.length > 0) {
      availableFields.forEach(field => {
        const sourceNode = nodes.find(n => n.type === 'source')
        params.set(field.name, {
          name: field.name,
          sourceNode: sourceNode?.id || 'source',
          sourceNodeLabel: getNodeLabel(sourceNode),
          dataType: field.type || 'unknown',
          origin: 'source'
        })
      })
    }

    // Extract from field_selector nodes (if they select fields)
    nodes.forEach(node => {
      if (node.type === 'field_selector' && node.config?.selected_fields) {
        node.config.selected_fields.forEach(fieldName => {
          if (!params.has(fieldName)) {
            params.set(fieldName, {
              name: fieldName,
              sourceNode: node.id,
              sourceNodeLabel: getNodeLabel(node),
              dataType: inferDataType(fieldName, availableFields),
              origin: 'field_selector'
            })
          }
        })
      }
    })

    // Extract from pipeline results if available
    if (pipelineResults?.final_data && pipelineResults.final_data.length > 0) {
      const firstRecord = pipelineResults.final_data[0]
      if (typeof firstRecord === 'object' && firstRecord !== null) {
        Object.keys(firstRecord).forEach(key => {
          if (!params.has(key)) {
            params.set(key, {
              name: key,
              sourceNode: 'destination',
              sourceNodeLabel: 'Destination Output',
              dataType: inferDataTypeFromValue(firstRecord[key]),
              origin: 'results'
            })
          }
        })
      }
    }

    return Array.from(params.values())
  }, [nodes, availableFields, pipelineResults])

  // Get current visualization config or initialize
  const config = visualizationConfig || {
    selected_fields: [],
    order: [],
    visibility: {}
  }

  const selectedFields = config.selected_fields || []
  const order = config.order || selectedFields
  const visibility = config.visibility || {}

  // Ensure order matches selected_fields
  const orderedSelectedFields = useMemo(() => {
    const ordered = order.filter(f => selectedFields.includes(f))
    const newFields = selectedFields.filter(f => !order.includes(f))
    return [...ordered, ...newFields]
  }, [selectedFields, order])

  // Available (not selected) parameters
  const availableParams = useMemo(() => {
    return availableParameters.filter(p => !selectedFields.includes(p.name))
  }, [availableParameters, selectedFields])

  const handleDragStart = (event) => {
    setActiveId(event.active.id)
    dragStartRef.current = true
  }

  const handleDragEnd = (event) => {
    const { active, over } = event

    if (!over) {
      setActiveId(null)
      return
    }

    const activeId = active.id
    const overId = over.id

    // Handle drag from available to selected (drop on dropzone or any selected item)
    if (activeId.startsWith('available-') && (overId === 'selected-dropzone' || overId.startsWith('selected-'))) {
      const paramName = activeId.replace('available-', '')
      if (!selectedFields.includes(paramName)) {
        let newOrder = [...order]
        // If dropping on a specific item, insert before it
        if (overId.startsWith('selected-')) {
          const targetIndex = orderedSelectedFields.findIndex(f => f === overId.replace('selected-', ''))
          if (targetIndex !== -1) {
            newOrder = [...orderedSelectedFields.slice(0, targetIndex), paramName, ...orderedSelectedFields.slice(targetIndex)]
          } else {
            newOrder = [...order, paramName]
          }
        } else {
          newOrder = [...order, paramName]
        }
        
        onConfigChange({
          selected_fields: [...selectedFields, paramName],
          order: newOrder,
          visibility: { ...visibility, [paramName]: true }
        })
      }
    }
    // Handle reordering within selected
    else if (activeId.startsWith('selected-') && overId.startsWith('selected-')) {
      const activeIndex = orderedSelectedFields.findIndex(f => f === activeId.replace('selected-', ''))
      const overIndex = orderedSelectedFields.findIndex(f => f === overId.replace('selected-', ''))

      if (activeIndex !== -1 && overIndex !== -1 && activeIndex !== overIndex) {
        const newOrder = arrayMove(orderedSelectedFields, activeIndex, overIndex)
        onConfigChange({
          ...config,
          order: newOrder
        })
      }
    }
    // Handle drag from selected to available (remove)
    else if (activeId.startsWith('selected-') && (overId === 'available-dropzone' || overId.startsWith('available-'))) {
      const paramName = activeId.replace('selected-', '')
      const newSelected = selectedFields.filter(f => f !== paramName)
      const newOrder = order.filter(f => f !== paramName)
      const newVisibility = { ...visibility }
      delete newVisibility[paramName]

      onConfigChange({
        selected_fields: newSelected,
        order: newOrder,
        visibility: newVisibility
      })
    }

    // Reset after a brief delay to allow click handlers to check
    const wasDrag = dragStartRef.current
    dragStartRef.current = false
    setActiveId(null)
    
    // Small delay to reset drag flag
    setTimeout(() => {
      dragStartRef.current = false
    }, 50)
  }

  const toggleVisibility = (paramName) => {
    onConfigChange({
      ...config,
      visibility: {
        ...visibility,
        [paramName]: !visibility[paramName]
      }
    })
  }

  const removeField = (paramName) => {
    const newSelected = selectedFields.filter(f => f !== paramName)
    const newOrder = order.filter(f => f !== paramName)
    const newVisibility = { ...visibility }
    delete newVisibility[paramName]

    onConfigChange({
      selected_fields: newSelected,
      order: newOrder,
      visibility: newVisibility
    })
  }

  const addField = (paramName) => {
    if (!selectedFields.includes(paramName)) {
      onConfigChange({
        selected_fields: [...selectedFields, paramName],
        order: [...order, paramName],
        visibility: { ...visibility, [paramName]: true }
      })
    }
  }

  const getActiveParam = () => {
    if (!activeId) return null
    if (activeId.startsWith('available-')) {
      return availableParams.find(p => p.name === activeId.replace('available-', ''))
    }
    if (activeId.startsWith('selected-')) {
      return availableParameters.find(p => p.name === activeId.replace('selected-', ''))
    }
    return null
  }

  if (isCollapsed) {
    return (
      <div className="viz-params-panel collapsed">
        <button
          className="viz-params-toggle"
          onClick={() => setIsCollapsed(false)}
          title="Expand Visualization Parameters"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 4h12M2 8h12M2 12h12"/>
          </svg>
          {selectedFields.length > 0 && (
            <span className="viz-params-badge">{selectedFields.length}</span>
          )}
        </button>
      </div>
    )
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="viz-params-panel">
        <div className="viz-params-header">
          <div className="viz-params-header-left">
            <h3 className="viz-params-title">Visualization Parameters</h3>
            {selectedFields.length > 0 && (
              <span className="viz-params-count">{selectedFields.length} selected</span>
            )}
          </div>
          <button
            className="viz-params-close"
            onClick={() => setIsCollapsed(true)}
            title="Collapse panel"
          >
            ×
          </button>
        </div>

        <div className="viz-params-content">
          {/* Available Parameters Section */}
          <div className="viz-params-section">
            <div className="viz-params-section-header">
              <span className="viz-params-section-title">Available Parameters</span>
              <span className="viz-params-section-count">{availableParams.length}</span>
            </div>
            <div
              id="available-dropzone"
              className="viz-params-list available-list"
            >
              {availableParams.length === 0 ? (
                <div className="viz-params-empty">
                  {availableParameters.length === 0 ? (
                    <>
                      <p>No parameters available</p>
                      <p className="viz-params-empty-hint">
                        Configure a source node and run the pipeline to see available parameters
                      </p>
                    </>
                  ) : (
                    <p>All parameters are selected</p>
                  )}
                </div>
              ) : (
                availableParams.map(param => (
                  <DraggableParameterItem
                    key={`available-${param.name}`}
                    id={`available-${param.name}`}
                    param={param}
                    type="available"
                    onHover={onNodeHover}
                    onAdd={() => addField(param.name)}
                    dragStartRef={dragStartRef}
                  />
                ))
              )}
            </div>
          </div>

          {/* Selected Parameters Section */}
          <div className="viz-params-section">
            <div className="viz-params-section-header">
              <span className="viz-params-section-title">Selected for Visualization</span>
              <span className="viz-params-section-count">{selectedFields.length}</span>
            </div>
            <div
              id="selected-dropzone"
              className="viz-params-list selected-list"
            >
              {orderedSelectedFields.length === 0 ? (
                <div className="viz-params-empty">
                  <p>No parameters selected</p>
                  <p className="viz-params-empty-hint">
                    Drag parameters from above or click to add them to visualization
                  </p>
                </div>
              ) : (
                <SortableContext
                  items={orderedSelectedFields.map(f => `selected-${f}`)}
                  strategy={verticalListSortingStrategy}
                >
                  {orderedSelectedFields.map(paramName => {
                    const param = availableParameters.find(p => p.name === paramName)
                    if (!param) return null
                    return (
                      <SortableParameterItem
                        key={`selected-${paramName}`}
                        id={`selected-${paramName}`}
                        param={param}
                        type="selected"
                        isVisible={visibility[paramName] !== false}
                        onToggleVisibility={() => toggleVisibility(paramName)}
                        onRemove={() => removeField(paramName)}
                        onHover={onNodeHover}
                      />
                    )
                  })}
                </SortableContext>
              )}
            </div>
          </div>
        </div>

        <DragOverlay>
          {activeId && getActiveParam() ? (
            <ParameterItem
              param={getActiveParam()}
              type={activeId.startsWith('available-') ? 'available' : 'selected'}
              isDragging
            />
          ) : null}
        </DragOverlay>
      </div>
    </DndContext>
  )
}

// Sortable Parameter Item Component
function SortableParameterItem({ id, param, type, isVisible, onToggleVisibility, onRemove, onHover }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`viz-param-item ${type} ${isDragging ? 'dragging' : ''}`}
      onMouseEnter={() => onHover && onHover(param.sourceNode)}
      onMouseLeave={() => onHover && onHover(null)}
    >
      <div className="viz-param-drag-handle" {...attributes} {...listeners}>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="2" cy="2" r="1"/>
          <circle cx="6" cy="2" r="1"/>
          <circle cx="10" cy="2" r="1"/>
          <circle cx="2" cy="6" r="1"/>
          <circle cx="6" cy="6" r="1"/>
          <circle cx="10" cy="6" r="1"/>
          <circle cx="2" cy="10" r="1"/>
          <circle cx="6" cy="10" r="1"/>
          <circle cx="10" cy="10" r="1"/>
        </svg>
      </div>
      <div className="viz-param-content">
        <div className="viz-param-header">
          <span className="viz-param-name">{param.name}</span>
          {type === 'selected' && (
            <div className="viz-param-actions">
              <button
                className={`viz-param-toggle ${isVisible ? 'visible' : 'hidden'}`}
                onClick={(e) => {
                  e.stopPropagation()
                  onToggleVisibility()
                }}
                title={isVisible ? 'Hide' : 'Show'}
              >
                {isVisible ? '👁' : '👁‍🗨'}
              </button>
              <button
                className="viz-param-remove"
                onClick={(e) => {
                  e.stopPropagation()
                  onRemove()
                }}
                title="Remove"
              >
                ×
              </button>
            </div>
          )}
        </div>
        <div className="viz-param-meta">
          <span className="viz-param-source" title={param.sourceNode}>
            {param.sourceNodeLabel}
          </span>
          <span className="viz-param-type">{param.dataType}</span>
        </div>
      </div>
    </div>
  )
}

// Draggable Parameter Item Component (for available list)
function DraggableParameterItem({ id, param, type, onHover, onAdd, dragStartRef }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    isDragging
  } = useDraggable({ id })
  const clickRef = useRef({ x: 0, y: 0, time: 0 })

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1
  }

  const handlePointerDown = (e) => {
    clickRef.current = {
      x: e.clientX,
      y: e.clientY,
      time: Date.now()
    }
  }

  const handlePointerUp = (e) => {
    if (isDragging) return
    
    const deltaX = Math.abs(e.clientX - clickRef.current.x)
    const deltaY = Math.abs(e.clientY - clickRef.current.y)
    const deltaTime = Date.now() - clickRef.current.time
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY)

    // If movement was less than 8px and happened quickly, treat as click
    if (distance < 8 && deltaTime < 300 && !dragStartRef?.current && onAdd) {
      e.preventDefault()
      e.stopPropagation()
      onAdd()
    }
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`viz-param-item ${type} ${isDragging ? 'dragging' : ''}`}
      onMouseEnter={() => onHover && onHover(param.sourceNode)}
      onMouseLeave={() => onHover && onHover(null)}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
    >
      <div 
        className="viz-param-drag-handle" 
        {...attributes} 
        {...listeners}
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="2" cy="2" r="1"/>
          <circle cx="6" cy="2" r="1"/>
          <circle cx="10" cy="2" r="1"/>
          <circle cx="2" cy="6" r="1"/>
          <circle cx="6" cy="6" r="1"/>
          <circle cx="10" cy="6" r="1"/>
          <circle cx="2" cy="10" r="1"/>
          <circle cx="6" cy="10" r="1"/>
          <circle cx="10" cy="10" r="1"/>
        </svg>
      </div>
      <div className="viz-param-content">
        <div className="viz-param-header">
          <span className="viz-param-name">{param.name}</span>
        </div>
        <div className="viz-param-meta">
          <span className="viz-param-source" title={param.sourceNode}>
            {param.sourceNodeLabel}
          </span>
          <span className="viz-param-type">{param.dataType}</span>
        </div>
      </div>
    </div>
  )
}

// Regular Parameter Item Component (for drag overlay)
function ParameterItem({ param, type, isDragging = false }) {
  return (
    <div
      className={`viz-param-item ${type} ${isDragging ? 'dragging' : ''}`}
      style={{ opacity: isDragging ? 0.5 : 1 }}
    >
      <div className="viz-param-drag-handle">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="2" cy="2" r="1"/>
          <circle cx="6" cy="2" r="1"/>
          <circle cx="10" cy="2" r="1"/>
          <circle cx="2" cy="6" r="1"/>
          <circle cx="6" cy="6" r="1"/>
          <circle cx="10" cy="6" r="1"/>
          <circle cx="2" cy="10" r="1"/>
          <circle cx="6" cy="10" r="1"/>
          <circle cx="10" cy="10" r="1"/>
        </svg>
      </div>
      <div className="viz-param-content">
        <div className="viz-param-header">
          <span className="viz-param-name">{param.name}</span>
        </div>
        <div className="viz-param-meta">
          <span className="viz-param-source" title={param.sourceNode}>
            {param.sourceNodeLabel}
          </span>
          <span className="viz-param-type">{param.dataType}</span>
        </div>
      </div>
    </div>
  )
}

// Helper functions
function getNodeLabel(node) {
  if (!node) return 'Unknown'
  const type = node.type
  if (type === 'source' && node.config?.connector_id) {
    return node.config.connector_id
  }
  const labels = {
    source: 'Source',
    field_selector: 'Field Selector',
    filter: 'Filter',
    transform: 'Transform',
    destination: 'Destination'
  }
  return labels[type] || type
}

function inferDataType(fieldName, availableFields) {
  const field = availableFields.find(f => f.name === fieldName)
  return field?.type || 'unknown'
}

function inferDataTypeFromValue(value) {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'string') {
    // Try to detect if it's a date
    if (!isNaN(Date.parse(value)) && value.length > 10) return 'datetime'
    return 'string'
  }
  if (Array.isArray(value)) return 'array'
  if (typeof value === 'object') return 'object'
  return 'unknown'
}

export default VisualizationParametersPanel