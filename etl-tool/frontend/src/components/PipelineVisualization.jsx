import { useState, useMemo, useEffect } from 'react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts'
import './PipelineVisualization.css'

const CHART_TYPES = {
  line: { label: 'Line Chart', icon: '📈' },
  bar: { label: 'Bar Chart', icon: '📊' },
  area: { label: 'Area Chart', icon: '📉' },
  scatter: { label: 'Scatter Plot', icon: '⚫' },
  pie: { label: 'Pie Chart', icon: '🥧' },
  table: { label: 'Table View', icon: '📋' }
}

const COLORS = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444', 
  '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'
]

// Helper function to convert values to numbers if possible
function convertToNumberIfPossible(value, fieldName = '') {
  if (value === null || value === undefined) {
    return value
  }
  
  // If already a number, return it
  if (typeof value === 'number' && !isNaN(value)) {
    return value
  }
  
  // Convert boolean to number
  if (typeof value === 'boolean') {
    return value ? 1 : 0
  }
  
  // If string, try to convert
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (trimmed === '' || trimmed === 'null' || trimmed === 'undefined') {
      return null
    }
    
    // Try parsing as number
    const numValue = parseFloat(trimmed)
    if (!isNaN(numValue) && isFinite(numValue)) {
      return numValue
    }
    
    // Check if field name suggests it should be numeric
    const fieldLower = fieldName.toLowerCase()
    if (fieldLower.includes('numeric') || 
        fieldLower.includes('price') || 
        fieldLower.includes('volume') ||
        fieldLower.includes('count') ||
        fieldLower.includes('amount') ||
        fieldLower.includes('value') ||
        fieldLower.includes('total') ||
        fieldLower.includes('sum') ||
        fieldLower.includes('avg') ||
        fieldLower.includes('min') ||
        fieldLower.includes('max')) {
      // Force conversion attempt
      const forced = parseFloat(trimmed.replace(/[^0-9.-]/g, ''))
      if (!isNaN(forced) && isFinite(forced)) {
        return forced
      }
    }
  }
  
  return value
}

function PipelineVisualization({ pipelineResults, visualizationConfig, availableFields = [] }) {
  const [chartType, setChartType] = useState('table')
  const [xAxisField, setXAxisField] = useState('')
  const [groupByField, setGroupByField] = useState('')

  const config = visualizationConfig || {
    selected_fields: [],
    order: [],
    visibility: {}
  }

  const selectedFields = config.selected_fields || []
  const visibility = config.visibility || {}
  const visibleFields = selectedFields.filter(field => visibility[field] !== false)

  // Extract data from pipeline results
  const chartData = useMemo(() => {
    // Try multiple possible data locations
    let data = null
    
    if (pipelineResults?.final_data && Array.isArray(pipelineResults.final_data)) {
      data = pipelineResults.final_data
    } else if (pipelineResults?.data && Array.isArray(pipelineResults.data)) {
      data = pipelineResults.data
    } else if (pipelineResults?.results?.data && Array.isArray(pipelineResults.results.data)) {
      data = pipelineResults.results.data
    } else if (Array.isArray(pipelineResults)) {
      data = pipelineResults
    }
    
    if (!data || !Array.isArray(data) || data.length === 0) {
      console.warn('📊 No data found in pipelineResults:', {
        hasPipelineResults: !!pipelineResults,
        final_data: pipelineResults?.final_data,
        data: pipelineResults?.data,
        resultsData: pipelineResults?.results?.data
      })
      return []
    }

    // If no fields selected, use all available fields from first record
    if (visibleFields.length === 0 && data.length > 0) {
      const firstRecord = data[0]
      if (typeof firstRecord === 'object' && firstRecord !== null) {
        return data.map((row, idx) => {
          const processed = { index: idx }
          Object.keys(row).forEach(key => {
            processed[key] = convertToNumberIfPossible(row[key], key)
          })
          return processed
        })
      }
    }

    // Filter to only visible selected fields, but convert all values
    const result = data.map((row, idx) => {
      const filtered = { index: idx }
      
      if (visibleFields.length === 0) {
        // If no visible fields, include all fields
        Object.keys(row).forEach(key => {
          filtered[key] = convertToNumberIfPossible(row[key], key)
        })
      } else {
        // Only include visible selected fields
        visibleFields.forEach(field => {
          // Try exact match first
          if (row.hasOwnProperty(field)) {
            const value = convertToNumberIfPossible(row[field], field)
            filtered[field] = value
          } else {
            // Try case-insensitive match
            const fieldLower = field.toLowerCase()
            const matchingKey = Object.keys(row).find(k => k.toLowerCase() === fieldLower)
            if (matchingKey) {
              const value = convertToNumberIfPossible(row[matchingKey], field)
              filtered[field] = value
            }
          }
        })
      }
      
      return filtered
    })
    
    return result
  }, [pipelineResults, visibleFields])

  // Get numeric fields for charts - check multiple rows for robustness
  const numericFields = useMemo(() => {
    if (chartData.length === 0) return []
    
    // Check multiple rows to determine numeric fields (handle cases where first row might be null/string)
    const fieldTypes = {}
    const sampleSize = Math.min(chartData.length, 10) // Check up to 10 rows
    
    chartData.slice(0, sampleSize).forEach(row => {
      Object.keys(row).forEach(key => {
        if (key === 'index') return
        
        const value = row[key]
        if (value !== null && value !== undefined) {
          if (!fieldTypes.hasOwnProperty(key)) {
            fieldTypes[key] = { numeric: 0, nonNumeric: 0 }
          }
          
          if (typeof value === 'number' && !isNaN(value)) {
            fieldTypes[key].numeric++
          } else {
            fieldTypes[key].nonNumeric++
          }
        }
      })
    })
    
    // A field is numeric if most of its values are numbers
    return Object.keys(fieldTypes).filter(key => {
      const stats = fieldTypes[key]
      const total = stats.numeric + stats.nonNumeric
      // Consider numeric if at least 50% of values are numbers, or if it has numeric in the name
      return (total > 0 && stats.numeric / total >= 0.5) || 
             key.toLowerCase().includes('numeric') ||
             key.toLowerCase().includes('price') ||
             key.toLowerCase().includes('volume') ||
             key.toLowerCase().includes('count') ||
             key.toLowerCase().includes('amount') ||
             key.toLowerCase().includes('value') ||
             key.toLowerCase().includes('total')
    })
  }, [chartData])

  // Debug: Log chart data and numeric fields
  useEffect(() => {
    if (chartData.length > 0) {
      console.log('📊 Visualization Data:', {
        totalRows: chartData.length,
        firstRow: chartData[0],
        numericFields,
        visibleFields,
        selectedFields
      })
    }
  }, [chartData, numericFields, visibleFields, selectedFields])

  // Get all available fields from chart data
  const allFields = useMemo(() => {
    if (chartData.length === 0) return []
    return Object.keys(chartData[0] || {}).filter(key => key !== 'index')
  }, [chartData])

  // Get string/categorical fields for grouping/categories
  const stringFields = useMemo(() => {
    if (chartData.length === 0) return []
    const firstRow = chartData[0]
    return Object.keys(firstRow).filter(key => {
      if (key === 'index') return false
      const value = firstRow[key]
      return typeof value === 'string' || (typeof value === 'object' && value !== null && !Array.isArray(value))
    })
  }, [chartData])

  // Auto-select x-axis if not set
  useEffect(() => {
    if (chartData.length > 0) {
      if (!xAxisField) {
        // Prefer string fields, but fall back to first numeric field or index
        if (stringFields.length > 0) {
          setXAxisField(stringFields[0])
        } else if (numericFields.length > 0) {
          setXAxisField(numericFields[0])
        } else if (allFields.length > 0) {
          setXAxisField(allFields[0])
        } else {
          setXAxisField('index')
        }
      }
    }
  }, [xAxisField, stringFields, numericFields, allFields, chartData.length])

  if (!pipelineResults) {
    return (
      <div className="pipeline-viz-empty">
        <div className="viz-empty-icon">📊</div>
        <h3>No Data Available</h3>
        <p>Run the pipeline first to see visualizations</p>
      </div>
    )
  }

  // Check if we have any data at all
  if (chartData.length === 0) {
    return (
      <div className="pipeline-viz-empty">
        <div className="viz-empty-icon">📋</div>
        <h3>No Data Available</h3>
        <p>No data found in pipeline results. Make sure the pipeline executed successfully.</p>
        <p style={{ fontSize: '12px', color: '#9CA3AF', marginTop: '8px' }}>
          Debug: pipelineResults = {pipelineResults ? 'exists' : 'null'}, 
          final_data = {pipelineResults?.final_data ? `exists (${Array.isArray(pipelineResults.final_data) ? pipelineResults.final_data.length : 'not array'})` : 'null'}
        </p>
      </div>
    )
  }

  if (visibleFields.length === 0 && allFields.length === 0) {
    return (
      <div className="pipeline-viz-empty">
        <div className="viz-empty-icon">📋</div>
        <h3>No Fields Available</h3>
        <p>Select parameters in the Visualization Parameters panel to create charts</p>
      </div>
    )
  }

  const renderChart = () => {
    if (chartType === 'table') {
      return (
        <div className="viz-table-container">
          <table className="viz-data-table">
            <thead>
              <tr>
                {visibleFields.length > 0 ? (
                  visibleFields.map(field => (
                    <th key={field}>{field}</th>
                  ))
                ) : (
                  Object.keys(chartData[0] || {}).filter(k => k !== 'index').map(key => (
                    <th key={key}>{key}</th>
                  ))
                )}
              </tr>
            </thead>
            <tbody>
              {chartData.slice(0, 100).map((row, idx) => (
                <tr key={idx}>
                  {visibleFields.length > 0 ? (
                    visibleFields.map(field => (
                      <td key={field}>
                        {row[field] !== undefined && row[field] !== null 
                          ? (typeof row[field] === 'object' 
                              ? JSON.stringify(row[field]).substring(0, 50) 
                              : String(row[field]).substring(0, 50))
                          : '-'}
                      </td>
                    ))
                  ) : (
                    Object.keys(chartData[0] || {}).filter(k => k !== 'index').map(key => (
                      <td key={key}>
                        {row[key] !== undefined && row[key] !== null 
                          ? (typeof row[key] === 'object' 
                              ? JSON.stringify(row[key]).substring(0, 50) 
                              : String(row[key]).substring(0, 50))
                          : '-'}
                      </td>
                    ))
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {chartData.length > 100 && (
            <div className="viz-table-footer">
              Showing first 100 of {chartData.length} rows
            </div>
          )}
        </div>
      )
    }

    if (chartType === 'pie' && numericFields.length > 0 && xAxisField) {
      // Aggregate data for pie chart
      const aggregated = {}
      chartData.forEach(row => {
        const key = String(row[xAxisField] || 'Unknown')
        numericFields.forEach(field => {
          if (!aggregated[key]) aggregated[key] = {}
          aggregated[key][field] = (aggregated[key][field] || 0) + (row[field] || 0)
        })
      })
      
      const pieData = Object.entries(aggregated).map(([name, values]) => ({
        name: name.substring(0, 20),
        ...values
      }))

      return (
        <ResponsiveContainer width="100%" height={400}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ name, value }) => `${name}: ${value?.toFixed(2) || 0}`}
              outerRadius={120}
              fill="#8884d8"
              dataKey={numericFields[0] || 'value'}
            >
              {pieData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )
    }

    if (numericFields.length === 0) {
      return (
        <div className="pipeline-viz-empty">
          <div className="viz-empty-icon">⚠️</div>
          <h3>No Numeric Data</h3>
          <p>Select numeric fields to create charts. Current chart types require numeric values.</p>
        </div>
      )
    }

    const fieldsToChart = numericFields.slice(0, 8) // Limit to 8 series for readability

    switch (chartType) {
      case 'line':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xAxisField || 'index'} />
              <YAxis />
              <Tooltip />
              <Legend />
              {fieldsToChart.map((field, idx) => (
                <Line
                  key={field}
                  type="monotone"
                  dataKey={field}
                  stroke={COLORS[idx % COLORS.length]}
                  name={field}
                  dot={false}
                  strokeWidth={2}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )

      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xAxisField || 'index'} />
              <YAxis />
              <Tooltip />
              <Legend />
              {fieldsToChart.map((field, idx) => (
                <Bar
                  key={field}
                  dataKey={field}
                  fill={COLORS[idx % COLORS.length]}
                  name={field}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )

      case 'area':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xAxisField || 'index'} />
              <YAxis />
              <Tooltip />
              <Legend />
              {fieldsToChart.map((field, idx) => (
                <Area
                  key={field}
                  type="monotone"
                  dataKey={field}
                  stackId={groupByField ? field : "1"}
                  stroke={COLORS[idx % COLORS.length]}
                  fill={COLORS[idx % COLORS.length]}
                  name={field}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        )

      case 'scatter':
        if (numericFields.length >= 2) {
          const scatterXField = xAxisField && numericFields.includes(xAxisField) ? xAxisField : numericFields[0]
          const scatterYField = groupByField && numericFields.includes(groupByField) ? groupByField : numericFields[1]
          
          return (
            <ResponsiveContainer width="100%" height={400}>
              <ScatterChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" dataKey={scatterXField} name={scatterXField} />
                <YAxis type="number" dataKey={scatterYField} name={scatterYField} />
                <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                <Legend />
                <Scatter name="Data Points" data={chartData} fill={COLORS[0]} />
              </ScatterChart>
            </ResponsiveContainer>
          )
        }
        return (
          <div className="pipeline-viz-empty">
            <div className="viz-empty-icon">⚠️</div>
            <h3>Need 2 Numeric Fields</h3>
            <p>Scatter plots require at least 2 numeric fields. Currently found: {numericFields.length}</p>
          </div>
        )

      default:
        return (
          <div className="pipeline-viz-empty">
            <div className="viz-empty-icon">📊</div>
            <h3>Chart Not Available</h3>
            <p>Select a different chart type</p>
          </div>
        )
    }
  }

  return (
    <div className="pipeline-visualization">
      <div className="viz-controls">
        <div className="viz-control-group">
          <label>Chart Type:</label>
          <div className="viz-chart-type-buttons">
            {Object.entries(CHART_TYPES).map(([type, info]) => (
              <button
                key={type}
                className={`viz-chart-type-btn ${chartType === type ? 'active' : ''}`}
                onClick={() => setChartType(type)}
                title={info.label}
              >
                <span className="viz-chart-icon">{info.icon}</span>
                <span className="viz-chart-label">{info.label}</span>
              </button>
            ))}
          </div>
        </div>

        {chartType !== 'table' && (
          <div className="viz-control-group">
            <label>X-Axis:</label>
            <select
              value={xAxisField || 'index'}
              onChange={(e) => setXAxisField(e.target.value)}
              className="viz-control-select"
            >
              <option value="index">Index (Row Number)</option>
              {allFields.map(field => (
                <option key={field} value={field}>{field}</option>
              ))}
            </select>
          </div>
        )}

        {chartType === 'pie' && (
          <div className="viz-control-group">
            <label>Category Field (for Pie Chart):</label>
            <select
              value={xAxisField || ''}
              onChange={(e) => setXAxisField(e.target.value)}
              className="viz-control-select"
            >
              <option value="">Select field...</option>
              {allFields.map(field => (
                <option key={field} value={field}>{field}</option>
              ))}
            </select>
          </div>
        )}

        {chartType === 'scatter' && numericFields.length >= 2 && (
          <>
            <div className="viz-control-group">
              <label>X-Axis (Numeric):</label>
              <select
                value={xAxisField || numericFields[0]}
                onChange={(e) => setXAxisField(e.target.value)}
                className="viz-control-select"
              >
                {numericFields.map(field => (
                  <option key={field} value={field}>{field}</option>
                ))}
              </select>
            </div>
            <div className="viz-control-group">
              <label>Y-Axis (Numeric):</label>
              <select
                value={groupByField || numericFields[1]}
                onChange={(e) => setGroupByField(e.target.value)}
                className="viz-control-select"
              >
                {numericFields.map(field => (
                  <option key={field} value={field}>{field}</option>
                ))}
              </select>
            </div>
          </>
        )}

        <div className="viz-info">
          <span className="viz-info-item">
            📊 {visibleFields.length || allFields.length} field{(visibleFields.length || allFields.length) !== 1 ? 's' : ''} available
          </span>
          <span className="viz-info-item">
            📈 {numericFields.length} numeric field{numericFields.length !== 1 ? 's' : ''}
          </span>
          <span className="viz-info-item">
            📋 {chartData.length} data point{chartData.length !== 1 ? 's' : ''}
          </span>
          {allFields.length > 0 && (
            <span className="viz-info-item" title={allFields.join(', ')}>
              🔤 {allFields.length} total field{allFields.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      <div className="viz-chart-container">
        {renderChart()}
      </div>
    </div>
  )
}

export default PipelineVisualization