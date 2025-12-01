import { useState } from 'react'
import './Header.css'
import HistoryModal from './HistoryModal'

function Header({ sidebarOpen, setIsOpen, history, onClearHistory }) {
  const [historyOpen, setHistoryOpen] = useState(false)

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

