import { useState, useRef, useEffect } from 'react'
import './Header.css'
import HistoryModal from './HistoryModal'

function Header({ sidebarOpen, setIsOpen, history, onClearHistory, user, onLogout }) {
  const [historyOpen, setHistoryOpen] = useState(false)
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false)
  const profileRef = useRef(null)

  // Get user initials from full name
  const getInitials = (fullName) => {
    if (!fullName) return 'U'
    const parts = fullName.trim().split(' ')
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    }
    return fullName.substring(0, 2).toUpperCase()
  }

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setProfileDropdownOpen(false)
      }
    }
    if (profileDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [profileDropdownOpen])

  const handleLogout = () => {
    setProfileDropdownOpen(false)
    if (onLogout) {
      onLogout()
    }
  }

  return (
    <>
      <header className="app-header">
        <div className={`header-content ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
          <button 
            className="header-menu-toggle"
            onClick={() => setIsOpen(!sidebarOpen)}
            aria-label="Toggle sidebar"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>
          <div className="header-logo">
            <h1>ETL Tool</h1>
            <p>Data Extraction & Transformation</p>
          </div>
          <div className="header-right-actions">
            <button 
              className="header-history-toggle"
              onClick={() => setHistoryOpen(true)}
              aria-label="View history"
              title="Extraction History"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 3h7v7H3z"></path>
                <path d="M14 3h7v7h-7z"></path>
                <path d="M14 14h7v7h-7z"></path>
                <path d="M3 14h7v7H3z"></path>
              </svg>
              {history.length > 0 && (
                <span className="history-badge">{history.length}</span>
              )}
            </button>
            {user && (
              <div className="profile-indicator" ref={profileRef}>
                <div 
                  className="profile-avatar"
                  onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
                  title={`Signed in as ${user.email}${user.full_name ? ` (${user.full_name})` : ''}`}
                >
                  <span className="avatar-initials">{getInitials(user.full_name || user.email)}</span>
                </div>
                {profileDropdownOpen && (
                  <div className="profile-dropdown">
                    <div className="profile-dropdown-item" onClick={handleLogout}>
                      Logout
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </header>
      <HistoryModal 
        isOpen={historyOpen} 
        onClose={() => setHistoryOpen(false)}
        history={history}
        onClearHistory={onClearHistory}
      />
    </>
  )
}

export default Header

