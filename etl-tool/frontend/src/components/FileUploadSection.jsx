import { useState, useEffect } from 'react'
import './Section.css'
import './FileUploadSection.css'
import { checkBackendHealth } from '../utils/backendCheck'
import { parseFlexibleJSON } from '../utils/jsonParser'
import { removeDuplicates } from '../utils/duplicateRemover'
import { downloadCSV, downloadJSON, downloadXLSX } from '../utils/downloadUtils'
import * as XLSX from 'xlsx'

function FileUploadSection({ data, setData }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [inputPreview, setInputPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [backendOnline, setBackendOnline] = useState(false)
  const [checkingBackend, setCheckingBackend] = useState(true)
  const [processingResults, setProcessingResults] = useState(null)
  const [progress, setProgress] = useState({
    extract: { time: 0, status: 'idle' },
    transform: { time: 0, status: 'idle' },
    load: { time: 0, status: 'idle' }
  })

  useEffect(() => {
    const verifyBackend = async () => {
      setCheckingBackend(true)
      const isOnline = await checkBackendHealth()
      setBackendOnline(isOnline)
      setCheckingBackend(false)
      if (!isOnline) {
        setError('Backend server is not running. Please start the backend server.')
      }
    }
    verifyBackend()
    // Check backend every 5 seconds
    const interval = setInterval(verifyBackend, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file) {
      setSelectedFile(file)
      setError(null)
      setProcessingResults(null)
      setInputPreview(null)
      
      // Read file for preview
      const fileType = file.name.split('.').pop().toLowerCase()
      if (fileType === 'csv' || fileType === 'json' || fileType === 'xlsx') {
        const reader = new FileReader()
        reader.onload = (e) => {
          try {
            if (fileType === 'xlsx') {
              try {
                const data = new Uint8Array(e.target.result)
                const workbook = XLSX.read(data, { type: 'array' })
                const firstSheetName = workbook.SheetNames[0]
                const worksheet = workbook.Sheets[firstSheetName]
                const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: '' })
                
                if (jsonData.length > 0) {
                  const headers = jsonData[0].map(h => String(h || ''))
                  const previewRows = []
                  for (let i = 1; i < Math.min(11, jsonData.length); i++) {
                    const row = jsonData[i]
                    const obj = {}
                    headers.forEach((header, index) => {
                      obj[header] = row[index] !== undefined ? String(row[index]) : ''
                    })
                    previewRows.push(obj)
                  }
                  
                  setInputPreview({
                    columns: headers,
                    rows: previewRows,
                    totalRows: jsonData.length - 1,
                    fileType: 'XLSX'
                  })
                }
              } catch (xlsxError) {
                console.error('Error reading XLSX file for preview:', xlsxError)
              }
            } else if (fileType === 'csv') {
              const text = e.target.result
              const lines = text.split('\n').filter(line => line.trim())
              if (lines.length > 0) {
                const parseCSVLine = (line) => {
                  const result = []
                  let current = ''
                  let inQuotes = false
                  for (let i = 0; i < line.length; i++) {
                    const char = line[i]
                    if (char === '"') {
                      if (inQuotes && line[i + 1] === '"') {
                        current += '"'
                        i++
                      } else {
                        inQuotes = !inQuotes
                      }
                    } else if (char === ',' && !inQuotes) {
                      result.push(current.trim())
                      current = ''
                    } else {
                      current += char
                    }
                  }
                  result.push(current.trim())
                  return result
                }
                
                const headers = parseCSVLine(lines[0])
                const previewRows = []
                for (let i = 1; i < Math.min(11, lines.length); i++) {
                  const values = parseCSVLine(lines[i])
                  const obj = {}
                  headers.forEach((header, index) => {
                    obj[header] = values[index] || ''
                  })
                  previewRows.push(obj)
                }
                
                setInputPreview({
                  columns: headers,
                  rows: previewRows,
                  totalRows: lines.length - 1,
                  fileType: 'CSV'
                })
              }
            } else if (fileType === 'json') {
              const text = e.target.result
              const parseResult = parseFlexibleJSON(text)
              if (parseResult && Array.isArray(parseResult.data) && parseResult.data.length > 0) {
                const allKeys = Object.keys(parseResult.data[0] || {})
                const previewRows = parseResult.data.slice(0, 10)
                
                setInputPreview({
                  columns: allKeys,
                  rows: previewRows,
                  totalRows: parseResult.data.length,
                  fileType: 'JSON'
                })
              }
            }
          } catch (err) {
            console.error('Error reading file for preview:', err)
          }
        }
        if (fileType === 'xlsx') {
          reader.readAsArrayBuffer(file)
        } else {
          reader.readAsText(file)
        }
      }
    }
  }

  const handleProcessFile = async () => {
    if (!selectedFile) {
      setError('Please select a file')
      return
    }

    // Check backend before proceeding
    const isOnline = await checkBackendHealth()
    if (!isOnline) {
      setError('Backend server is not running. Please start the backend server.')
      setBackendOnline(false)
      return
    }
    setBackendOnline(true)

    setLoading(true)
    setError(null)
    setProgress({
      extract: { time: 0, status: 'running' },
      transform: { time: 0, status: 'idle' },
      load: { time: 0, status: 'idle' }
    })

    const startTime = Date.now()
    const extractStartTime = Date.now()

    try {
      const fileType = selectedFile.name.split('.').pop().toLowerCase()
      
      if (fileType === 'csv' || fileType === 'json' || fileType === 'xlsx') {
        // Read file and extract data
        const reader = new FileReader()
        
        reader.onload = async (e) => {
          try {
            let extractedData = []
            let parseErrors = []
            let totalRows = 0
            let duplicateCount = 0
            
            // Extract phase
            if (fileType === 'xlsx') {
              try {
                const data = new Uint8Array(e.target.result)
                const workbook = XLSX.read(data, { type: 'array' })
                const firstSheetName = workbook.SheetNames[0]
                const worksheet = workbook.Sheets[firstSheetName]
                const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: '' })
                
                if (jsonData.length === 0) {
                  throw new Error('XLSX file is empty')
                }
                
                const headers = jsonData[0].map(h => String(h || ''))
                if (!headers || headers.length === 0) {
                  throw new Error('XLSX file has no headers')
                }
                
                totalRows = jsonData.length - 1
                
                const rows = []
                for (let i = 1; i < jsonData.length; i++) {
                  try {
                    const row = jsonData[i]
                    const obj = {}
                    headers.forEach((header, index) => {
                      obj[header] = row[index] !== undefined ? String(row[index]) : ''
                    })
                    rows.push(obj)
                  } catch (lineError) {
                    parseErrors.push({
                      line: i + 1,
                      error: lineError.message || 'Parse error',
                      content: JSON.stringify(jsonData[i]).substring(0, 100)
                    })
                  }
                }
                extractedData = rows
              } catch (xlsxError) {
                throw new Error(`XLSX parsing error: ${xlsxError.message}`)
              }
            } else if (fileType === 'csv') {
              try {
                const text = e.target.result
                if (!text || text.trim().length === 0) {
                  throw new Error('CSV file is empty')
                }
                
                const lines = text.split('\n').filter(line => line.trim())
                
                if (lines.length === 0) {
                  throw new Error('CSV file is empty')
                }
                
                // Handle CSV with proper quote handling
                const parseCSVLine = (line) => {
                  const result = []
                  let current = ''
                  let inQuotes = false
                  
                  for (let i = 0; i < line.length; i++) {
                    const char = line[i]
                    if (char === '"') {
                      if (inQuotes && line[i + 1] === '"') {
                        current += '"'
                        i++ // Skip next quote
                      } else {
                        inQuotes = !inQuotes
                      }
                    } else if (char === ',' && !inQuotes) {
                      result.push(current.trim())
                      current = ''
                    } else {
                      current += char
                    }
                  }
                  result.push(current.trim())
                  return result
                }
                
                const headers = parseCSVLine(lines[0])
                if (!headers || headers.length === 0) {
                  throw new Error('CSV file has no headers')
                }
                
                totalRows = lines.length - 1
                
                const rows = []
                for (let i = 1; i < lines.length; i++) {
                  try {
                    const values = parseCSVLine(lines[i])
                    const obj = {}
                    headers.forEach((header, index) => {
                      obj[header] = values[index] || ''
                    })
                    rows.push(obj)
                  } catch (lineError) {
                    parseErrors.push({
                      line: i + 1,
                      error: lineError.message || 'Parse error',
                      content: lines[i] ? lines[i].substring(0, 100) : ''
                    })
                  }
                }
                extractedData = rows
              } catch (csvError) {
                throw new Error(`CSV parsing error: ${csvError.message}`)
              }
            } else if (fileType === 'json') {
              try {
                const text = e.target.result
                if (!text || text.trim().length === 0) {
                  throw new Error('JSON file is empty')
                }
                
                const parseResult = parseFlexibleJSON(text)
                if (!parseResult || !Array.isArray(parseResult.data)) {
                  throw new Error('Invalid JSON structure')
                }
                extractedData = parseResult.data || []
                parseErrors = parseResult.errors || []
                totalRows = extractedData.length
              } catch (jsonError) {
                throw new Error(`JSON parsing error: ${jsonError.message}`)
              }
            }
            
            // Validate extracted data
            if (!Array.isArray(extractedData)) {
              extractedData = []
            }
            
            if (extractedData.length === 0 && parseErrors.length === 0) {
              throw new Error('No data extracted from file. File may be empty or in an unsupported format.')
            }

            const extractTime = ((Date.now() - extractStartTime) / 1000).toFixed(2)
            setProgress(prev => ({
              ...prev,
              extract: { time: extractTime, status: 'completed' },
              transform: { time: 0, status: 'running' }
            }))

            // Transform phase - Remove duplicates and refine data
            await new Promise(resolve => setTimeout(resolve, 500))
            const transformStartTime = Date.now()
            
            let uniqueData = extractedData
            try {
              const dedupeResult = removeDuplicates(extractedData)
              if (dedupeResult && dedupeResult.uniqueData) {
                uniqueData = dedupeResult.uniqueData
                duplicateCount = dedupeResult.duplicateCount || 0
              }
            } catch (dedupeError) {
              console.warn('Duplicate removal failed, using original data:', dedupeError)
              // Continue with original data if deduplication fails
            }
            
            // Refine data: clean and normalize
            let refinedData = uniqueData.map(row => {
              const cleanedRow = {}
              for (const [key, value] of Object.entries(row)) {
                // Trim whitespace from strings
                if (typeof value === 'string') {
                  cleanedRow[key] = value.trim()
                } else {
                  cleanedRow[key] = value
                }
              }
              return cleanedRow
            }).filter(row => {
              // Remove rows where all values are empty
              const hasData = Object.values(row).some(val => 
                val !== null && val !== undefined && val !== ''
              )
              return hasData
            })
            
            extractedData = refinedData
            
            const transformTime = ((Date.now() - transformStartTime) / 1000).toFixed(2)
            
            setProgress(prev => ({
              ...prev,
              transform: { time: transformTime, status: 'completed' },
              load: { time: 0, status: 'running' }
            }))

            // Load phase (simulate)
            await new Promise(resolve => setTimeout(resolve, 300))
            const loadStartTime = Date.now()
            const loadTime = ((Date.now() - loadStartTime) / 1000).toFixed(2)
            const totalTime = ((Date.now() - startTime) / 1000).toFixed(2)

            setProgress(prev => ({
              ...prev,
              load: { time: loadTime, status: 'completed' }
            }))

            // Ensure data is valid before setting
            const finalData = Array.isArray(extractedData) ? extractedData : []
            
            // Prepare processing results
            const results = {
              success: true,
              rows_processed: finalData.length,
              rows_before: totalRows,
              duplicateCount: duplicateCount,
              output_file: `${selectedFile.name.replace(/\.[^/.]+$/, '')}_processed.${fileType}`,
              results: {
                steps: {
                  EXTRACT: {
                    status: 'success',
                    data_size: `${totalRows} elements`
                  },
                  LOAD: {
                    status: 'success'
                  },
                  TRANSFORM_1: {
                    status: 'success',
                    data_size: `${finalData.length} elements`,
                    transformer: 'FunctionTransformer'
                  }
                }
              },
              preview: finalData.slice(0, 10),
              columns: finalData.length > 0 ? Object.keys(finalData[0]) : []
            }
            
            setProcessingResults(results)
            
            try {
              setData({
                source: 'File Upload',
                fileType: fileType.toUpperCase(),
                fileName: selectedFile.name,
                data: finalData,
                totalRows: finalData.length,
                duplicateCount: duplicateCount,
                parseErrors: parseErrors.length > 0 ? parseErrors : undefined,
                timestamp: new Date().toISOString(),
                progress: {
                  extract: extractTime,
                  transform: transformTime,
                  load: loadTime,
                  total: totalTime
                },
              })
              
              // Show errors if any, but don't block the data display
              if (parseErrors.length > 0) {
                setError(`⚠️ File extracted with ${parseErrors.length} parsing error(s). Data still available.`)
              } else {
                setError(null)
              }
            } catch (setDataError) {
              console.error('Error setting data:', setDataError)
              throw new Error(`Failed to process extracted data: ${setDataError.message}`)
            }
          } catch (parseError) {
            console.error('File parsing error:', parseError)
            setError(`Error parsing file: ${parseError.message || 'Unknown error occurred'}`)
            setProgress({
              extract: { time: 0, status: 'failed' },
              transform: { time: 0, status: 'idle' },
              load: { time: 0, status: 'idle' }
            })
            // Don't set data if there's an error
            setData(null)
          } finally {
            setLoading(false)
          }
        }

        reader.onerror = () => {
          setError('Error reading file')
          setLoading(false)
          setProgress({
            extract: { time: 0, status: 'failed' },
            transform: { time: 0, status: 'idle' },
            load: { time: 0, status: 'idle' }
          })
        }

        if (fileType === 'xlsx') {
          reader.readAsArrayBuffer(selectedFile)
        } else {
          reader.readAsText(selectedFile)
        }
      } else {
        setError('Unsupported file type. Please upload CSV, JSON, or XLSX files.')
        setLoading(false)
      }
    } catch (err) {
      setError(`Error: ${err.message}`)
      setLoading(false)
    }
  }

  const handleDownload = () => {
    if (!processingResults) return
    
    // Prioritize full processed data from state, fallback to preview
    const downloadData = (data && data.data && Array.isArray(data.data) && data.data.length > 0) 
      ? data.data 
      : (processingResults.preview && Array.isArray(processingResults.preview) && processingResults.preview.length > 0)
        ? processingResults.preview
        : []
    
    if (!downloadData || downloadData.length === 0) {
      setError('No data available for download')
      return
    }
    
    const fileType = selectedFile.name.split('.').pop().toLowerCase()
    const filename = processingResults.output_file || `${selectedFile.name.replace(/\.[^/.]+$/, '')}_processed.${fileType}`
    
    if (fileType === 'csv') {
      downloadCSV(downloadData, filename)
    } else if (fileType === 'xlsx') {
      downloadXLSX(downloadData, filename)
    } else {
      downloadJSON(downloadData, filename)
    }
  }

  return (
    <div className="section-container">
      <div className="section-header">
        <h2>📁 File Upload Section</h2>
        <p>Upload CSV, JSON, XLSX or stored files for extraction</p>
      </div>

      <div className="section-content">
        <div className="upload-area">
          <div className="file-upload-row">
            <input
              type="file"
              id="file-upload"
              accept=".csv,.json,.xlsx"
              onChange={handleFileChange}
              className="file-input"
            />
            <label htmlFor="file-upload" className="file-label">
              {selectedFile ? selectedFile.name : 'Choose File (CSV/JSON/XLSX)'}
            </label>
            
            <button 
              onClick={handleProcessFile} 
              disabled={!selectedFile || loading || !backendOnline}
              className="file-label extract-data-btn"
            >
              {loading ? 'Processing...' : 'Process File'}
            </button>
          </div>
          
          {selectedFile && (
            <div className="file-info">
              <p>File: {selectedFile.name}</p>
              <p>Size: {(selectedFile.size / 1024).toFixed(2)} KB</p>
              <p>Type: {selectedFile.type || selectedFile.name.split('.').pop().toUpperCase()}</p>
            </div>
          )}

          {error && <div className="error-message">{error}</div>}
        </div>

        {/* Input Data Preview - Only show before processing starts */}
        {inputPreview && !processingResults && !loading && (
          <div className="input-preview-section">
            <div className="preview-header">
              <h3>Input Data Preview</h3>
              <div className="preview-stats">
                <span>Rows: <strong>{inputPreview.totalRows}</strong></span>
                <span>Columns: <strong>{inputPreview.columns.length} columns</strong></span>
              </div>
            </div>
            <div className="preview-table-container">
              <p className="preview-label">Preview (First 10 rows)</p>
              <table className="preview-table">
                <thead>
                  <tr>
                    {inputPreview.columns.map((col, idx) => (
                      <th key={idx}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {inputPreview.rows.map((row, rowIdx) => (
                    <tr key={rowIdx}>
                      {inputPreview.columns.map((col, colIdx) => (
                        <td key={colIdx}>{row[col]?.toString() || ''}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Processing Results - Only show after processing */}
        {processingResults && (
          <div className="processing-results-section">
            <h3>Processing Results</h3>
            <div className="success-message">
              <span className="success-icon">✓</span>
              <span>Success Pipeline completed successfully</span>
            </div>

            {/* Pipeline Steps */}
            <div className="pipeline-steps-section">
              <h4>Pipeline Steps</h4>
              <div className="steps-grid">
                <div className="step-card">
                  <div className="step-header-row">
                    <span className="step-name">EXTRACT</span>
                    <span className="step-status success">✓</span>
                  </div>
                  <p className="step-detail">Size: {processingResults.results.steps.EXTRACT.data_size}</p>
                </div>
                <div className="step-card">
                  <div className="step-header-row">
                    <span className="step-name">LOAD</span>
                    <span className="step-status success">✓</span>
                  </div>
                  <p className="step-detail">Rows Processed: {processingResults.rows_processed}</p>
                </div>
                <div className="step-card">
                  <div className="step-header-row">
                    <span className="step-name">TRANSFORM 1</span>
                    <span className="step-status success">✓</span>
                  </div>
                  <p className="step-detail">Size: {processingResults.results.steps.TRANSFORM_1.data_size}</p>
                  <p className="step-detail">Transformer: {processingResults.results.steps.TRANSFORM_1.transformer}</p>
                </div>
              </div>
            </div>

            {/* Output Preview - Removed: Only Real-Time Ingested Data should be visible after processing */}
          </div>
        )}
      </div>
    </div>
  )
}

export default FileUploadSection

