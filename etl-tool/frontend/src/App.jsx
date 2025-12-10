import { useState, useEffect } from 'react'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import FileUploadSection from './components/FileUploadSection'
import APISection from './components/APISection'
import WebSocketSection from './components/WebSocketSection'
import VisualizationSection from './components/VisualizationSection'
import DataDisplay from './components/DataDisplay'
import ErrorBoundary from './components/ErrorBoundary'
import AuthForm from './components/AuthForm'
import './App.css'

function App() {
  const [activeSection, setActiveSection] = useState('files')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sectionData, setSectionData] = useState({
    files: null,
    api: null,
    websocket: null
  })
  const [history, setHistory] = useState([])
  const [token, setToken] = useState(() => localStorage.getItem('etl-auth-token') || '')
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState('')
  // Default to backend on 8000; can be overridden via VITE_API_BASE
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

  const authFetch = async (path, options = {}) => {
    const resp = await fetch(`${apiBase}${path}`, {
      ...options,
      headers: {
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      }
    })
    if (!resp.ok) {
      const text = await resp.text()
      throw new Error(text || `Request failed with ${resp.status}`)
    }
    return resp
  }

  const loadProfile = async (incomingToken) => {
    const usableToken = incomingToken || token
    if (!usableToken) return
    try {
      setAuthLoading(true)
      const resp = await fetch(`${apiBase}/auth/me`, {
        headers: { Authorization: `Bearer ${usableToken}` }
      })
      if (!resp.ok) throw new Error('Not authenticated')
      const data = await resp.json()
      setUser(data)
      setToken(usableToken)
      localStorage.setItem('etl-auth-token', usableToken)
      setAuthError('')
    } catch (err) {
      console.error(err)
      setUser(null)
      setToken('')
      localStorage.removeItem('etl-auth-token')
      setAuthError('Session expired. Please log in again.')
    } finally {
      setAuthLoading(false)
    }
  }

  useEffect(() => {
    if (token) {
      loadProfile(token)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Load history from localStorage on mount
  useEffect(() => {
    try {
      const savedHistory = localStorage.getItem('etl-history')
      if (savedHistory) {
        const parsed = JSON.parse(savedHistory)
        if (Array.isArray(parsed)) {
          setHistory(parsed)
        }
      }
    } catch (e) {
      console.error('Failed to load history:', e)
      // Clear corrupted history
      try {
        localStorage.removeItem('etl-history')
      } catch (clearError) {
        console.error('Failed to clear corrupted history:', clearError)
      }
    }
  }, [])

  // Save history to localStorage whenever it changes
  useEffect(() => {
    if (history.length === 0) {
      try {
        localStorage.removeItem('etl-history')
      } catch (e) {
        console.warn('Failed to clear history:', e)
      }
      return
    }

    try {
      const historyString = JSON.stringify(history)
      // Check size before saving (localStorage limit is usually 5-10MB)
      if (historyString.length > 4 * 1024 * 1024) { // 4MB limit
        console.warn('History too large, truncating...')
        // Keep only the most recent 10 items
        const truncated = history.slice(0, 10)
        localStorage.setItem('etl-history', JSON.stringify(truncated))
        setHistory(truncated)
      } else {
        localStorage.setItem('etl-history', historyString)
      }
    } catch (e) {
      if (e.name === 'QuotaExceededError' || e.code === 22) {
        console.warn('localStorage quota exceeded, clearing old history')
        // Try to save with fewer items
        try {
          const reduced = history.slice(0, 5) // Keep only 5 most recent
          localStorage.setItem('etl-history', JSON.stringify(reduced))
          setHistory(reduced)
        } catch (e2) {
          console.error('Failed to save reduced history:', e2)
          // Clear history if still failing
          try {
            localStorage.removeItem('etl-history')
            setHistory([])
          } catch (e3) {
            console.error('Failed to clear history:', e3)
          }
        }
      } else {
        console.error('Error saving history:', e)
      }
    }
  }, [history])

  const updateSectionData = (section, data) => {
    setSectionData(prev => ({
      ...prev,
      [section]: data
    }))
    
    // Add to history if data is from File Upload or API sections
    // IMPORTANT: Don't store full data in history - only metadata
    if (data && (section === 'files' || section === 'api')) {
      const historyItem = {
        id: Date.now() + Math.random(),
        source: data.source || 'File Upload',
        fileType: data.fileType,
        fileName: data.fileName,
        url: data.url,
        timestamp: data.timestamp || new Date().toISOString(),
        totalRows: data.totalRows,
        duplicateCount: data.duplicateCount,
        // DO NOT store the full data array - it's too large for localStorage
        // The actual data is stored in sectionData, history is just for reference
        dataPreview: Array.isArray(data.data) && data.data.length > 0 
          ? { 
              sample: data.data.slice(0, 1), // Store only first row as preview
              totalCount: data.data.length 
            }
          : null
      }
      
      setHistory(prev => {
        const newHistory = [historyItem, ...prev].slice(0, 20) // Reduced to 20 items max
        return newHistory
      })
    }
  }

  const clearHistory = () => {
    setHistory([])
    localStorage.removeItem('etl-history')
  }

  const handleLogin = async ({ email, password }) => {
    setAuthLoading(true)
    setAuthError('')
    try {
      const body = new URLSearchParams()
      body.append('username', email)
      body.append('password', password)
      const resp = await fetch(`${apiBase}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body
      })
      if (!resp.ok) {
        const text = await resp.text()
        throw new Error(text || 'Login failed')
      }
      const data = await resp.json()
      const accessToken = data.access_token
      if (!accessToken) throw new Error('Token missing in response')
      setToken(accessToken)
      await loadProfile(accessToken)
    } catch (err) {
      console.error(err)
      setAuthError(err.message || 'Login failed')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleRegister = async ({ email, password, fullName }) => {
    setAuthLoading(true)
    setAuthError('')
    try {
      const resp = await fetch(`${apiBase}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, full_name: fullName })
      })
      if (!resp.ok) {
        const text = await resp.text()
        throw new Error(text || 'Registration failed')
      }
      // Auto-login after successful registration
      await handleLogin({ email, password })
    } catch (err) {
      console.error(err)
      setAuthError(err.message || 'Registration failed')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = async () => {
    try {
      await authFetch('/auth/logout', { method: 'POST' })
    } catch (err) {
      console.warn('Logout error (ignored):', err)
    }
    setUser(null)
    setToken('')
    localStorage.removeItem('etl-auth-token')
  }

  const renderActiveSection = () => {
    switch (activeSection) {
      case 'files':
        return (
          <FileUploadSection
            data={sectionData.files}
            setData={(data) => updateSectionData('files', data)}
          />
        )
      case 'api':
        return (
          <APISection
            data={sectionData.api}
            setData={(data) => updateSectionData('api', data)}
          />
        )
      case 'websocket':
        return (
          <WebSocketSection
            data={sectionData.websocket}
            setData={(data) => updateSectionData('websocket', data)}
          />
        )
      case 'visualization':
        return (
          <VisualizationSection />
        )
      default:
        return null
    }
  }

  return (
    <ErrorBoundary>
      <div className="App">
        {!user ? (
          <div className="auth-screen">
            <div className="auth-card">
              <h1 className="auth-title">ETL Tool</h1>
              <p className="auth-subtitle">Log in or create an account to continue</p>
              <AuthForm
                loading={authLoading}
                error={authError}
                onLogin={handleLogin}
                onRegister={handleRegister}
              />
            </div>
          </div>
        ) : (
          <>
            <Header 
              sidebarOpen={sidebarOpen} 
              setIsOpen={setSidebarOpen}
              history={history}
              onClearHistory={clearHistory}
            />
            <Sidebar 
              activeSection={activeSection} 
              setActiveSection={setActiveSection}
              isOpen={sidebarOpen}
              setIsOpen={setSidebarOpen}
            />
            
            <main className={`App-main ${sidebarOpen ? 'sidebar-open' : ''}`}>
              <div className="auth-bar">
                <div>
                  Signed in as <strong>{user.email}</strong>{user.full_name ? ` (${user.full_name})` : ''}
                </div>
                <button className="logout-btn" onClick={handleLogout}>Logout</button>
              </div>
              <div className="main-content">
                <div className="section-panel">
                  {renderActiveSection()}
                </div>
                
                {/* Show DataDisplay for File Upload and API sections when sectionData exists */}
                {activeSection !== 'websocket' && sectionData[activeSection] && (
                  <div className="data-panel" style={{ 
                    width: '100%', 
                    marginTop: '20px',
                    padding: '20px',
                    backgroundColor: '#fff',
                    borderRadius: '8px',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                    minHeight: '400px'
                  }}>
                    {(() => {
                      try {
                        // Always render DataDisplay if sectionData exists for this section
                        // DataDisplay will handle showing empty state or table
                        console.log('🔄 Rendering DataDisplay for section:', activeSection)
                        const currentSectionData = sectionData[activeSection]
                        console.log('📊 Section data:', {
                          hasData: !!currentSectionData.data,
                          dataLength: Array.isArray(currentSectionData.data) ? currentSectionData.data.length : 'not array',
                          dataType: typeof currentSectionData.data,
                          status: currentSectionData.status,
                          connector_id: currentSectionData.connector_id,
                          source: currentSectionData.source,
                          totalRows: currentSectionData.totalRows,
                          fullData: currentSectionData
                        })
                        
                        // CRITICAL: Ensure data is always an array
                        if (currentSectionData && currentSectionData.data && !Array.isArray(currentSectionData.data)) {
                          console.log('⚠️ Data is not an array, converting...')
                          currentSectionData.data = [currentSectionData.data]
                        }
                        
                        return <DataDisplay sectionData={currentSectionData} />
                      } catch (error) {
                        console.error('❌ Error rendering DataDisplay:', error)
                        return (
                          <div className="data-display empty">
                            <div className="empty-state">
                              <p>Error displaying data</p>
                              <p className="empty-hint">Please try extracting the file again</p>
                              <p className="empty-hint" style={{ fontSize: '0.8em', color: '#999' }}>
                                Error: {error.message}
                              </p>
                            </div>
                          </div>
                        )
                      }
                    })()}
                  </div>
                )}
              </div>
            </main>
          </>
        )}
      </div>
    </ErrorBoundary>
  )
}

export default App
