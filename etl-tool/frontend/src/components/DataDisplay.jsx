import { useState, useMemo, memo } from 'react'
import './DataDisplay.css'
import { downloadCSV, downloadJSON } from '../utils/downloadUtils'

function DataDisplay({ sectionData }) {
  // ALL HOOKS MUST BE CALLED BEFORE ANY CONDITIONAL RETURNS
  const [currentRowIndex, setCurrentRowIndex] = useState(0)
  const [displayStartIndex, setDisplayStartIndex] = useState(0)
  const rowsPerPage = 100

  // Safely extract properties with defaults - handle null/undefined sectionData
  const safeSectionData = sectionData || {}
  const { 
    source = 'Unknown', 
    data = null, 
    timestamp, 
    fileName, 
    fileType, 
    url, 
    mode, 
    messages, 
    progress, 
    totalMessages, 
    messagesPerSecond, 
    transformed, 
    totalRows, 
    duplicateCount, 
    parseErrors, 
    responseFormat, 
    contentType 
  } = safeSectionData

  // CRITICAL: Process data in useMemo - MUST be called before any early returns
  // This ensures hook count is consistent across renders
  const { isArray, dataLength, displayData, processedData } = useMemo(() => {
    let processed = data || null
    let isArr = false
    let length = 0
    let display = []
    
    try {
      // CRITICAL: Always ensure data is an array for table display
      if (processed === null || processed === undefined) {
        processed = []
      } else if (!Array.isArray(processed)) {
        // If it's not an array, try to convert it
        if (typeof processed === 'object') {
          processed = [processed]
        } else {
          processed = []
        }
      }
      
      isArr = Array.isArray(processed)
      length = isArr ? processed.length : 0
      
      // Safely slice the array
      if (isArr && length > 0) {
        const start = Math.max(0, displayStartIndex)
        const end = Math.min(start + rowsPerPage, length)
        display = processed.slice(start, end)
      } else {
        display = []
      }
    } catch (err) {
      console.error('Error processing data in useMemo:', err)
      processed = []
      isArr = true
      length = 0
      display = []
    }
    
    return {
      isArray: isArr,
      dataLength: length,
      displayData: display,
      processedData: processed
    }
  }, [data, displayStartIndex, rowsPerPage])
  
  // Use processedData for the rest of the component
  const tableData = processedData || []

  // Safety check for sectionData - AFTER all hooks are called
  if (!sectionData || typeof sectionData !== 'object') {
    console.log('❌ sectionData is null or not an object')
    return (
      <div className="data-display empty">
        <div className="empty-state">
          <p>No data extracted yet</p>
          <p className="empty-hint">Use the sections on the left to extract data</p>
        </div>
      </div>
    )
  }
  
  // CRITICAL: Ensure data is always an array
  if (sectionData.data && !Array.isArray(sectionData.data)) {
    console.log('⚠️ Data is not an array, converting to array...')
    sectionData.data = [sectionData.data]
  }
  
  console.log('📦 DataDisplay received sectionData:', {
    hasData: !!sectionData.data,
    dataType: typeof sectionData.data,
    dataIsArray: Array.isArray(sectionData.data),
    dataLength: Array.isArray(sectionData.data) ? sectionData.data.length : (sectionData.data ? 1 : 0),
    connector_id: sectionData.connector_id,
    status: sectionData.status,
    source: sectionData.source,
    totalRows: sectionData.totalRows,
    keys: Object.keys(sectionData),
    firstDataItem: Array.isArray(sectionData.data) && sectionData.data.length > 0 ? sectionData.data[0] : null
  })

  // Check if data exists (could be array or object)
  // Also check if connector is running (for real-time streams)
  const hasConnectorId = !!sectionData.connector_id
  const isRunning = sectionData.status === 'running'
  const isRealTimeStream = source === 'Real-Time API Stream' || hasConnectorId || isRunning
  
  // CRITICAL: Check if we have actual data (not just empty array)
  // Ensure data is an array first
  const dataArray = Array.isArray(data) ? data : (data ? [data] : [])
  const hasData = dataArray.length > 0
  
  // Also check totalRows as a fallback
  const hasTotalRows = sectionData.totalRows && sectionData.totalRows > 0
  
  console.log('🔍 Data check:', {
    dataExists: !!data,
    dataIsArray: Array.isArray(data),
    dataArrayLength: dataArray.length,
    hasData,
    hasTotalRows,
    totalRows: sectionData.totalRows
  })

  // Debug info
  console.log('🔍 DataDisplay render:', {
    source,
    hasData,
    hasConnectorId,
    isRunning,
    isRealTimeStream,
    dataLength: Array.isArray(data) ? data.length : (data ? 1 : 0),
    status: sectionData.status,
    connector_id: sectionData.connector_id,
    dataType: Array.isArray(data) ? 'array' : typeof data,
    dataIsEmptyArray: Array.isArray(data) && data.length === 0,
    fullSectionData: sectionData
  })

  // ALWAYS show table if ANY of these are true:
  // 1. Data exists (hasData is true) - THIS IS THE MOST IMPORTANT
  // 2. totalRows > 0 (data exists in database)
  // 3. Source is 'Real-Time API Stream', OR
  // 4. connector_id exists, OR
  // 5. status is 'running'
  // Only show empty state if NONE of the above are true
  const shouldShowTable = hasData || 
                          hasTotalRows ||
                          source === 'Real-Time API Stream' || 
                          hasConnectorId || 
                          isRunning ||
                          sectionData.status === 'running' ||
                          !!sectionData.connector_id
  
  console.log('🔍 Table visibility check:', {
    shouldShowTable,
    hasData,
    dataExists: !!data,
    dataIsArray: Array.isArray(data),
    dataLength: Array.isArray(data) ? data.length : 'not array',
    source,
    hasConnectorId,
    isRunning,
    status: sectionData.status,
    connector_id: sectionData.connector_id,
    willShowTable: shouldShowTable
  })
  
  // CRITICAL: If we have data, ALWAYS show table, no matter what
  if (hasData) {
    console.log('✅ HAS DATA - WILL SHOW TABLE')
  }
  
  // FORCE show table if connector_id exists OR status is running
  // This ensures table is ALWAYS visible when connector is active
  const forceShowTable = !!sectionData.connector_id || sectionData.status === 'running'
  
  if (!shouldShowTable && !forceShowTable) {
    console.log('❌ Showing empty state - none of the conditions met')
    console.log('❌ Debug details:', {
      hasData,
      source,
      hasConnectorId,
      isRunning,
      status: sectionData.status,
      connector_id: sectionData.connector_id,
      data: data,
      dataType: typeof data,
      forceShowTable
    })
    return (
      <div className="data-display empty">
        <div className="empty-state">
          <p>No data extracted yet</p>
          <p className="empty-hint">Use the sections on the left to extract data</p>
          <p className="empty-hint" style={{ fontSize: '0.8em', color: '#999', marginTop: '10px' }}>
            Debug: source={source}, connector_id={sectionData.connector_id || 'none'}, status={sectionData.status || 'none'}, hasData={hasData ? 'true' : 'false'}
          </p>
        </div>
      </div>
    )
  }
  
  // If forceShowTable is true, override shouldShowTable
  const finalShouldShowTable = shouldShowTable || forceShowTable
  
  if (forceShowTable && !shouldShowTable) {
    console.log('🔧 FORCING table display - connector is active')
  }
  
  console.log('✅ WILL SHOW TABLE - shouldShowTable:', finalShouldShowTable, 'hasData:', hasData, 'forceShowTable:', forceShowTable)
  
  console.log('📊 Data processing:', {
    isArray,
    dataLength,
    displayDataLength: displayData.length,
    hasData: tableData.length > 0,
    finalShouldShowTable
  })
  
  // Determine download format based on source
  const getDownloadFormat = () => {
    if (source === 'API Link' && responseFormat) {
      return responseFormat
    } else if (source === 'File Upload' && fileType) {
      return fileType.toLowerCase()
    }
    return 'json' // default
  }
  
  const downloadFormat = getDownloadFormat()
  
  const handleDownloadCSV = () => {
    const filename = fileName ? fileName.replace(/\.[^/.]+$/, '') + '_extracted.csv' : 'data.csv'
    downloadCSV(isArray ? tableData : [tableData], filename)
  }

  const handleDownloadJSON = () => {
    const filename = fileName ? fileName.replace(/\.[^/.]+$/, '') + '_extracted.json' : 'data.json'
    downloadJSON(isArray ? tableData : [tableData], filename)
  }
  
  const handleDownload = () => {
    if (downloadFormat === 'csv' || downloadFormat === 'CSV') {
      handleDownloadCSV()
    } else if (downloadFormat === 'xml' || downloadFormat === 'XML') {
      // For XML, download as text
      const xmlContent = typeof tableData[0]?.raw === 'string' ? tableData[0].raw : JSON.stringify(tableData, null, 2)
      const blob = new Blob([xmlContent], { type: 'application/xml;charset=utf-8;' })
      const link = document.createElement('a')
      const url = URL.createObjectURL(blob)
      link.setAttribute('href', url)
      link.setAttribute('download', fileName ? fileName.replace(/\.[^/.]+$/, '') + '_extracted.xml' : 'data.xml')
      link.style.visibility = 'hidden'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } else {
      handleDownloadJSON()
    }
  }

  return (
    <div className="data-display">
      <div className="data-header">
          <div className="data-source-info">
            <div className="header-top-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
              <h3>{finalShouldShowTable ? 'Real-Time Ingested Data' : source}</h3>
              {finalShouldShowTable && (sectionData.status === 'running' || sectionData.connector_id) && (
                <span style={{
                  color: '#ef4444',
                  fontSize: '0.9em',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px'
                }}>
                  <span style={{ 
                    width: '8px', 
                    height: '8px', 
                    borderRadius: '50%', 
                    backgroundColor: '#ef4444',
                    display: 'inline-block',
                    animation: 'pulse 2s infinite'
                  }}></span>
                  LIVE
                </span>
              )}
            </div>
          <div className="data-meta" style={{ display: 'flex', alignItems: 'center', gap: '15px', flexWrap: 'wrap' }}>
            {finalShouldShowTable && (
              <>
                <span style={{ color: '#4CAF50', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span style={{ fontSize: '12px' }}>●</span> Connected
                </span>
              </>
            )}
            {totalRows !== undefined && (
              <span>Total Records: <strong>{totalRows}</strong></span>
            )}
            {timestamp && (
              <span>Last Update: {new Date(timestamp).toLocaleTimeString()}</span>
            )}
            {fileName && <span className="meta-item">{fileName}</span>}
            {fileType && <span className="meta-item">Type: {fileType}</span>}
            {url && <span className="meta-item">{url}</span>}
            {mode && <span className="meta-item">{mode}</span>}
            {totalMessages !== undefined && (
              <span className="meta-item">Total Messages: <strong>{totalMessages}</strong></span>
            )}
            {messagesPerSecond !== undefined && (
              <span className="meta-item">Messages/sec: <strong>{messagesPerSecond}</strong></span>
            )}
            {transformed !== undefined && (
              <span className="meta-item">Transformed: <strong>{transformed}</strong></span>
            )}
            {timestamp && (
              <span className="meta-item">
                {new Date(timestamp).toLocaleString()}
              </span>
            )}
            {progress && (
              <>
                <span className="meta-item progress-time">
                  Extract: <strong>{progress.extract}s</strong>
                </span>
                <span className="meta-item progress-time">
                  Transform: <strong>{progress.transform}s</strong>
                </span>
                <span className="meta-item progress-time">
                  Load: <strong>{progress.load}s</strong>
                </span>
                <span className="meta-item progress-time">
                  Total: <strong>{progress.total}s</strong>
                </span>
              </>
            )}
          </div>
        </div>
        <div className="data-stats">
          {totalRows !== undefined && (
            <span className="stat-item">
              Total Rows: <strong>{totalRows}</strong>
            </span>
          )}
          {duplicateCount !== undefined && duplicateCount > 0 && (
            <span className="stat-item duplicate-stat">
              Duplicates Removed: <strong>{duplicateCount}</strong>
            </span>
          )}
          <span className="stat-item">
            Current Records: <strong>{dataLength}</strong>
          </span>
          {isArray && tableData.length > 0 && (
            <span className="stat-item">
              Fields: <strong>{Object.keys(tableData[0]).length}</strong>
            </span>
          )}
          {/* {isArray && data.length > rowsPerPage && (
            <span className="stat-item showing-info">
              Showing: <strong>{displayStartIndex + 1}</strong> - <strong>{Math.min(displayStartIndex + rowsPerPage, data.length)}</strong> of <strong>{data.length}</strong>
            </span>
          )} */}
          <div className="download-buttons">
            {(downloadFormat === 'csv' || downloadFormat === 'CSV') ? (
              <button onClick={handleDownloadCSV} className="download-btn" title="Download CSV">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                <span className="download-label">CSV</span>
              </button>
            ) : downloadFormat === 'xml' || downloadFormat === 'XML' ? (
              <button onClick={handleDownload} className="download-btn" title="Download XML">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                  <path d="M8 7h8"></path>
                  <path d="M8 11h8"></path>
                  <path d="M8 15h6"></path>
                </svg>
                <span className="download-label">XML</span>
              </button>
            ) : (
              <button onClick={handleDownloadJSON} className="download-btn" title="Download JSON">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                  <path d="M8 7h8"></path>
                  <path d="M8 11h8"></path>
                  <path d="M8 15h6"></path>
                </svg>
                <span className="download-label">JSON</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {parseErrors && parseErrors.length > 0 && (
        <div className="parse-errors-section">
          <h4>⚠️ Parsing Errors ({parseErrors.length})</h4>
          <div className="parse-errors-list">
            {parseErrors.slice(0, 10).map((error, idx) => (
              <div key={idx} className="parse-error-item">
                <span className="error-line">Line {error.line}:</span>
                <span className="error-message">{error.error}</span>
                {error.content && (
                  <span className="error-content">"{error.content}..."</span>
                )}
              </div>
            ))}
            {parseErrors.length > 10 && (
              <div className="parse-error-more">
                ... and {parseErrors.length - 10} more errors
              </div>
            )}
          </div>
        </div>
      )}

      <div className="data-content">
        {finalShouldShowTable && isArray ? (
          <div className="data-table-container">
            {tableData.length > rowsPerPage && (
              <div className="pagination-controls">
                <button 
                  onClick={() => setDisplayStartIndex(Math.max(0, displayStartIndex - rowsPerPage))}
                  disabled={displayStartIndex === 0}
                  className="pagination-btn"
                >
                  ← Previous
                </button>
                <span className="pagination-info">
                  Page {Math.floor(displayStartIndex / rowsPerPage) + 1} of {Math.ceil(tableData.length / rowsPerPage)}
                </span>
                <button 
                  onClick={() => setDisplayStartIndex(Math.min(tableData.length - rowsPerPage, displayStartIndex + rowsPerPage))}
                  disabled={displayStartIndex + rowsPerPage >= tableData.length}
                  className="pagination-btn"
                >
                  Next →
                </button>
              </div>
            )}
            <table className="data-table">
              <thead>
                <tr>
                  <th className="row-number">#</th>
                  {tableData && tableData[0] ? (
                    // Show all columns from data, but prioritize key columns
                    (() => {
                      const allKeys = Object.keys(tableData[0])
                      // Reorder to show important columns first
                      const priorityKeys = ['timestamp', 'session_id', 'source_id', 'processed_data', 'raw_data']
                      const orderedKeys = [
                        ...priorityKeys.filter(k => allKeys.includes(k)),
                        ...allKeys.filter(k => !priorityKeys.includes(k))
                      ]
                      return orderedKeys.map((key) => {
                        const isDataColumn = key === 'processed_data' || key === 'raw_data'
                        const isIdColumn = key === 'session_id' || key === 'source_id'
                        return (
                          <th 
                            key={key} 
                            className={isDataColumn ? 'data-column-header' : isIdColumn ? 'id-column-header' : ''}
                            data-column={key}
                          >
                            {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                          </th>
                        )
                      })
                    })()
                  ) : (
                    // Default columns if no data structure
                    <>
                      <th>Timestamp</th>
                      <th className="id-column-header">Session ID</th>
                      <th className="id-column-header">Source ID</th>
                      <th className="data-column-header">Processed Data</th>
                      <th className="data-column-header">Raw Data</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {tableData.length > 0 ? (
                  displayData.length > 0 ? displayData.map((row, index) => {
                  try {
                    const actualIndex = displayStartIndex + index
                    // Get row keys, prioritizing important columns
                    const allRowKeys = row ? Object.keys(row) : (tableData && tableData[0] ? Object.keys(tableData[0]) : [])
                    const priorityKeys = ['timestamp', 'session_id', 'source_id', 'processed_data', 'raw_data']
                    const rowKeys = [
                      ...priorityKeys.filter(k => allRowKeys.includes(k)),
                      ...allRowKeys.filter(k => !priorityKeys.includes(k))
                    ]
                    
                    return (
                      <tr 
                        key={row.id || row.source_id || `${actualIndex}-${tableData.length || 0}`}
                        className={actualIndex === currentRowIndex ? 'current-row' : ''}
                        onClick={() => setCurrentRowIndex(actualIndex)}
                        style={{ 
                          cursor: 'pointer',
                          borderBottom: '1px solid #eee'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f9f9f9'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                      >
                        <td className="row-number">
                          {actualIndex + 1}
                        </td>
                        {rowKeys.map((key) => {
                          try {
                            const value = row[key]
                            let displayValue = ''
                            let isLongText = false
                            
                            if (value === null || value === undefined) {
                              displayValue = ''
                            } else if (typeof value === 'object') {
                              // Format JSON objects nicely
                              try {
                                displayValue = JSON.stringify(value, null, 2)
                                isLongText = displayValue.length > 500
                              } catch {
                                displayValue = String(value)
                              }
                            } else if (typeof value === 'string' && value.length > 500) {
                              // Truncate very long strings
                              displayValue = value
                              isLongText = true
                            } else {
                              displayValue = String(value)
                            }
                            
                            // Special handling for processed_data and raw_data columns
                            const isDataColumn = key === 'processed_data' || key === 'raw_data'
                            const isSessionId = key === 'session_id' || key === 'source_id'
                            
                            // Truncate session_id and source_id for display
                            if (isSessionId && displayValue && displayValue.length > 16) {
                              displayValue = displayValue.substring(0, 16) + '...'
                            }
                            
                            // Determine cell class based on column type
                            let cellClassName = ''
                            if (isDataColumn) {
                              cellClassName = 'data-column'
                            } else if (isSessionId) {
                              cellClassName = 'id-column'
                            }
                            
                            return (
                              <td 
                                key={key}
                                data-column={key}
                                className={cellClassName}
                              >
                                {isLongText && !isDataColumn ? (
                                  <details style={{ cursor: 'pointer' }}>
                                    <summary style={{ color: '#2196F3', cursor: 'pointer' }}>
                                      {displayValue.substring(0, 100)}... (Click to expand)
                                    </summary>
                                    <pre className="scrollable-content" style={{ 
                                      margin: '5px 0 0 0', 
                                      whiteSpace: 'pre-wrap',
                                      fontFamily: 'monospace',
                                      fontSize: '0.8em',
                                      maxHeight: '300px',
                                      overflow: 'auto',
                                      backgroundColor: '#f5f5f5',
                                      padding: '10px',
                                      borderRadius: '4px'
                                    }}>{displayValue}</pre>
                                  </details>
                                ) : isDataColumn && displayValue.length > 200 ? (
                                  <details style={{ cursor: 'pointer' }}>
                                    <summary style={{ color: '#2196F3', cursor: 'pointer', fontSize: '0.8em' }}>
                                      {displayValue.substring(0, 150)}... (Click to expand)
                                    </summary>
                                    <pre style={{ 
                                      margin: '5px 0 0 0', 
                                      whiteSpace: 'pre-wrap',
                                      fontFamily: 'monospace',
                                      fontSize: '0.75em',
                                      maxHeight: '300px',
                                      overflow: 'auto',
                                      backgroundColor: '#f5f5f5',
                                      padding: '10px',
                                      borderRadius: '4px'
                                    }}>{displayValue}</pre>
                                  </details>
                                ) : (
                                  <pre className="scrollable-content" style={{ 
                                    margin: 0, 
                                    whiteSpace: 'pre-wrap',
                                    fontFamily: isDataColumn ? 'monospace' : 'inherit',
                                    fontSize: isDataColumn ? '0.75em' : '0.85em',
                                    maxHeight: isDataColumn ? '200px' : 'none',
                                    overflow: 'auto'
                                  }}>{displayValue}</pre>
                                )}
                              </td>
                            )
                          } catch (cellError) {
                            console.warn(`Error rendering cell ${key}:`, cellError)
                            return <td key={key} style={{ padding: '8px', border: '1px solid #ddd' }}>Error</td>
                          }
                        })}
                      </tr>
                    )
                  } catch (rowError) {
                    console.warn(`Error rendering row ${index}:`, rowError)
                    return (
                      <tr key={`error-${index}`}>
                        <td colSpan="100%" style={{ color: 'red', padding: '10px' }}>Error rendering row</td>
                      </tr>
                    )
                  }
                }) : (
                  <tr>
                    <td colSpan="100%" style={{ padding: '20px', textAlign: 'center', color: '#999' }}>
                      <p>⚠️ Data exists but displayData is empty</p>
                      <p style={{ fontSize: '0.9em', marginTop: '10px' }}>
                        data.length: {tableData.length}, displayStartIndex: {displayStartIndex}, rowsPerPage: {rowsPerPage}
                      </p>
                    </td>
                  </tr>
                )
                ) : (
                  <tr>
                    <td colSpan="100%" style={{ padding: '20px', textAlign: 'center', color: '#999' }}>
                      <p>🔄 Waiting for real-time data...</p>
                      <p style={{ fontSize: '0.9em', marginTop: '10px' }}>Connector is running. Data will appear here as it streams in.</p>
                      <p style={{ fontSize: '0.85em', marginTop: '10px', color: '#bbb' }}>
                        Status: {sectionData.status || 'unknown'} | Connector ID: {sectionData.connector_id || 'none'}
                      </p>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : finalShouldShowTable ? (
          // For real-time streams, show empty table structure
          <div className="data-table-container">
            <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ backgroundColor: '#f5f5f5', position: 'sticky', top: 0 }}>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>#</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Timestamp</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Session ID</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Source ID</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Processed Data</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Raw Data</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan="6" style={{ padding: '40px', textAlign: 'center', color: '#999' }}>
                    <p>🔄 Waiting for real-time data...</p>
                    <p style={{ fontSize: '0.9em', marginTop: '10px' }}>Connector is running. Data will appear here as it streams in.</p>
                    <p style={{ fontSize: '0.8em', marginTop: '5px', color: '#bbb' }}>
                      Debug: data={tableData ? (Array.isArray(tableData) ? `array[${tableData.length}]` : typeof tableData) : 'null'}
                    </p>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        ) : (
          <div className="data-json">
            <pre>{JSON.stringify(tableData, null, 2)}</pre>
          </div>
        )}
      </div>

    </div>
  )
}

// Memoize component with STRICT custom comparison to prevent flickering
export default memo(DataDisplay, (prevProps, nextProps) => {
  // Compare all relevant props to prevent unnecessary re-renders
  const prevData = prevProps?.sectionData?.data
  const nextData = nextProps?.sectionData?.data
  const prevConnectorId = prevProps?.sectionData?.connector_id
  const nextConnectorId = nextProps?.sectionData?.connector_id
  const prevStatus = prevProps?.sectionData?.status
  const nextStatus = nextProps?.sectionData?.status
  
  // If connector ID or status changed, re-render
  if (prevConnectorId !== nextConnectorId || prevStatus !== nextStatus) {
    return false
  }
  
  // If both data are null/undefined, they're equal
  if (!prevData && !nextData) return true
  if (!prevData || !nextData) return false
  
  // Compare arrays strictly
  if (Array.isArray(prevData) && Array.isArray(nextData)) {
    // If lengths differ, they're different
    if (prevData.length !== nextData.length) return false
    
    // If both empty, they're equal
    if (prevData.length === 0) return true
    
    // Compare first and last items by ID for quick check
    const prevFirstId = prevData[0]?.id
    const nextFirstId = nextData[0]?.id
    const prevLastId = prevData[prevData.length - 1]?.id
    const nextLastId = nextData[nextData.length - 1]?.id
    
    // If first or last items differ, they're different
    if (prevFirstId !== nextFirstId || prevLastId !== nextLastId) {
      return false
    }
    
    // Arrays appear the same, don't re-render (return true = props are equal)
    return true
  }
  
  // Not arrays or different types, they're different
  return false
})

