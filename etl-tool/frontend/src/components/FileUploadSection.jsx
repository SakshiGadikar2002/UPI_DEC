import { useState, useEffect } from 'react'
import './Section.css'
import { checkBackendHealth } from '../utils/backendCheck'
import { parseFlexibleJSON } from '../utils/jsonParser'
import { removeDuplicates } from '../utils/duplicateRemover'

function FileUploadSection({ data, setData }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [backendOnline, setBackendOnline] = useState(false)
  const [checkingBackend, setCheckingBackend] = useState(true)
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
        setError('Backend server is not running. Please start the backend server at http://localhost:8000')
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
    }
  }

  const handleExtract = async () => {
    if (!selectedFile) {
      setError('Please select a file')
      return
    }

    // Check backend before proceeding
    const isOnline = await checkBackendHealth()
    if (!isOnline) {
      setError('Backend server is not running. Please start the backend server at http://localhost:8000')
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
      
      if (fileType === 'csv' || fileType === 'json') {
        // Read file and extract data
        const reader = new FileReader()
        
        reader.onload = async (e) => {
          try {
            let extractedData = []
            let parseErrors = []
            let totalRows = 0
            let duplicateCount = 0
            
            // Extract phase
            if (fileType === 'csv') {
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

            // Transform phase - Remove duplicates
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
            
            extractedData = uniqueData
            
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

        reader.readAsText(selectedFile)
      } else {
        setError('Unsupported file type. Please upload CSV or JSON files.')
        setLoading(false)
      }
    } catch (err) {
      setError(`Error: ${err.message}`)
      setLoading(false)
    }
  }

  return (
    <div className="section-container">
      <div className="section-header">
        <h2>📁 File Upload Section</h2>
        <p>Upload CSV, JSON or stored files for extraction</p>
      </div>

      <div className="section-content">
        <div className="upload-area">
          <div className="file-upload-row">
            <input
              type="file"
              id="file-upload"
              accept=".csv,.json"
              onChange={handleFileChange}
              className="file-input"
            />
            <label htmlFor="file-upload" className="file-label">
              {selectedFile ? selectedFile.name : 'Choose File (CSV/JSON)'}
            </label>
            
            <button 
              onClick={handleExtract} 
              disabled={!selectedFile || loading || !backendOnline}
              className="file-label extract-data-btn"
            >
              {loading ? 'Extracting...' : 'Extract Data'}
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
      </div>
    </div>
  )
}

export default FileUploadSection

