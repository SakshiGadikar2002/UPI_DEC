import React, { useState, useRef, useEffect } from 'react'
import './SimpleFlow.css'

const SimpleFlow = ({ nodes, edges }) => {
  const containerRef = useRef(null)
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 })
  const [isDragging, setIsDragging] = useState(false)
  const [lastMousePos, setLastMousePos] = useState({ x: 0, y: 0 })
  const [containerSize, setContainerSize] = useState({ w: 0, h: 0 })

  // Calculate content bounds to center initially & get container size
  useEffect(() => {
    if (!containerRef.current) return
    
    // Update container size for minimap
    setContainerSize({
      w: containerRef.current.clientWidth,
      h: containerRef.current.clientHeight
    })

    if (nodes.length === 0) return

    const padding = 50
    const minX = Math.min(...nodes.map(n => n.position.x))
    const maxX = Math.max(...nodes.map(n => n.position.x + (n.style?.width || 160)))
    const minY = Math.min(...nodes.map(n => n.position.y))
    const maxY = Math.max(...nodes.map(n => n.position.y + 60))

    const contentWidth = maxX - minX + padding * 2
    const contentHeight = maxY - minY + padding * 2
    
    const containerWidth = containerRef.current.clientWidth
    const containerHeight = containerRef.current.clientHeight

    // Center the content
    const x = (containerWidth - contentWidth) / 2 - minX + padding
    const y = (containerHeight - contentHeight) / 2 - minY + padding

    // Only apply if it's the first load (scale is 1, x/y are 0)
    // We can check a flag or just assume initial mount
    if (transform.scale === 1 && transform.x === 0 && transform.y === 0) {
        const initialX = contentWidth > containerWidth ? 20 : x
        const initialY = contentHeight > containerHeight ? 20 : y
        setTransform({ x: initialX, y: initialY, scale: 1 })
    }
  }, [nodes])

  // Resize observer to keep container size updated
  useEffect(() => {
    if (!containerRef.current) return
    const ro = new ResizeObserver(entries => {
      for (let entry of entries) {
        setContainerSize({
          w: entry.contentRect.width,
          h: entry.contentRect.height
        })
      }
    })
    ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  const handleMouseDown = (e) => {
    // Only drag if clicking background (not nodes)
    if (e.target.closest('.flow-node')) return
    
    setIsDragging(true)
    setLastMousePos({ x: e.clientX, y: e.clientY })
  }

  const handleMouseMove = (e) => {
    if (!isDragging) return
    const dx = e.clientX - lastMousePos.x
    const dy = e.clientY - lastMousePos.y
    setTransform(prev => ({ ...prev, x: prev.x + dx, y: prev.y + dy }))
    setLastMousePos({ x: e.clientX, y: e.clientY })
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  const handleMouseLeave = () => {
    setIsDragging(false)
  }

  const handleZoomIn = (e) => {
    e.stopPropagation()
    setTransform(prev => ({ ...prev, scale: Math.min(prev.scale + 0.2, 3) }))
  }

  const handleZoomOut = (e) => {
    e.stopPropagation()
    setTransform(prev => ({ ...prev, scale: Math.max(prev.scale - 0.2, 0.2) }))
  }

  const getNodeCenter = (nodeId) => {
    const node = nodes.find(n => n.id === nodeId)
    if (!node) return { x: 0, y: 0 }
    const width = node.style?.width || 160
    const height = 60 // Approximate height
    return { x: node.position.x, y: node.position.y, w: width, h: height }
  }

  // MiniMap Data Calculation
  const getMiniMapData = () => {
    if (!nodes.length || containerSize.w === 0) return null

    const padding = 50
    const minX = Math.min(...nodes.map(n => n.position.x))
    const maxX = Math.max(...nodes.map(n => n.position.x + (n.style?.width || 160)))
    const minY = Math.min(...nodes.map(n => n.position.y))
    const maxY = Math.max(...nodes.map(n => n.position.y + 60))

    // World size including padding
    const worldW = (maxX - minX) + padding * 2
    const worldH = (maxY - minY) + padding * 2
    
    // MiniMap size (matches CSS)
    const mapW = 150
    const mapH = 100
    
    // Scale to fit world into minimap
    // Use Math.max for divisor to avoid division by zero
    const scale = Math.min(mapW / Math.max(worldW, 1), mapH / Math.max(worldH, 1)) * 0.8 // 0.8 to leave some margin
    
    // Calculate offsets to center the world in the minimap
    const mapContentW = worldW * scale
    const mapContentH = worldH * scale
    const offsetX = (mapW - mapContentW) / 2
    const offsetY = (mapH - mapContentH) / 2

    // Viewport rect calculation
    // Convert current view to world coordinates
    const viewWorldX = -transform.x / transform.scale
    const viewWorldY = -transform.y / transform.scale
    const viewWorldW = containerSize.w / transform.scale
    const viewWorldH = containerSize.h / transform.scale

    // Map world coords to minimap coords
    const viewportRect = {
        left: offsetX + (viewWorldX - (minX - padding)) * scale,
        top: offsetY + (viewWorldY - (minY - padding)) * scale,
        width: viewWorldW * scale,
        height: viewWorldH * scale
    }

    const miniNodes = nodes.map(n => ({
        id: n.id,
        left: offsetX + (n.position.x - minX + padding) * scale,
        top: offsetY + (n.position.y - minY + padding) * scale,
        width: (n.style?.width || 160) * scale,
        height: 60 * scale
    }))

    return { viewportRect, miniNodes }
  }

  const miniMapData = getMiniMapData()

  return (
    <div 
      className="simple-flow-container" 
      ref={containerRef}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
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
            className="flow-node" 
            style={{ 
              left: node.position.x, 
              top: node.position.y, 
              ...node.style 
            }}
          >
            {node.data.label}
          </div>
        ))}
      </div>

      {/* Controls */}
      <div className="simple-flow-controls-panel">
        <button className="simple-flow-control-btn" onClick={handleZoomIn} title="Zoom In">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
        </button>
        <button className="simple-flow-control-btn" onClick={handleZoomOut} title="Zoom Out">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
        </button>
      </div>

      {/* MiniMap */}
      {miniMapData && (
        <div className="simple-flow-minimap">
            <div className="simple-flow-minimap-content">
                {miniMapData.miniNodes.map(node => (
                    <div 
                        key={node.id}
                        className="simple-flow-minimap-node"
                        style={{
                            left: node.left,
                            top: node.top,
                            width: node.width,
                            height: node.height
                        }}
                    />
                ))}
                <div 
                    className="simple-flow-minimap-viewport"
                    style={{
                        left: miniMapData.viewportRect.left,
                        top: miniMapData.viewportRect.top,
                        width: miniMapData.viewportRect.width,
                        height: miniMapData.viewportRect.height
                    }}
                />
            </div>
        </div>
      )}
    </div>
  )
}

export default SimpleFlow
