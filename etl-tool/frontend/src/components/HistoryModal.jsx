import { useState } from 'react'
import { downloadCSV, downloadJSON } from '../utils/downloadUtils'
import './HistoryModal.css'

function HistoryModal({ isOpen, onClose, history, onClearHistory }) {
  const [selectedItem, setSelectedItem] = useState(null)

  if (!isOpen) return null

  const handleDownload = (item) => {
    // Check if data exists (new structure stores only preview)
    if (!item.data && !item.dataPreview) {
      alert('Data not available in history. Please extract the file again to download.')
      return
    }
    
    // Use preview data if full data is not available
    const dataToUse = item.data || (item.dataPreview?.sample || [])
    const isArray = Array.isArray(dataToUse)
    const dataToDownload = isArray ? dataToUse : [dataToUse]
    
    if (dataToDownload.length === 0) {
      alert('No data available to download. Please extract the file again.')
      return
    }
    
    try {
      if (item.fileType === 'CSV' || item.responseFormat === 'CSV' || item.responseFormat === 'csv') {
        const filename = item.fileName 
          ? item.fileName.replace(/\.[^/.]+$/, '') + '_extracted.csv' 
          : `history_${item.id}_extracted.csv`
        downloadCSV(dataToDownload, filename)
      } else if (item.responseFormat === 'XML' || item.responseFormat === 'xml') {
        const xmlContent = typeof dataToDownload[0]?.raw === 'string' ? dataToDownload[0].raw : JSON.stringify(dataToDownload, null, 2)
        const blob = new Blob([xmlContent], { type: 'application/xml;charset=utf-8;' })
        const link = document.createElement('a')
        const url = URL.createObjectURL(blob)
        link.setAttribute('href', url)
        link.setAttribute('download', item.fileName ? item.fileName.replace(/\.[^/.]+$/, '') + '_extracted.xml' : `history_${item.id}_extracted.xml`)
        link.style.visibility = 'hidden'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      } else {
        const filename = item.fileName 
          ? item.fileName.replace(/\.[^/.]+$/, '') + '_extracted.json' 
          : `history_${item.id}_extracted.json`
        downloadJSON(dataToDownload, filename)
      }
    } catch (error) {
      console.error('Error downloading history item:', error)
      alert('Error downloading file. Please try extracting the file again.')
    }
  }

  return (
    <div className="history-modal-overlay" onClick={onClose}>
      <div className="history-modal" onClick={(e) => e.stopPropagation()}>
        <div className="history-modal-header">
          <h2>Extraction History</h2>
          <div className="history-modal-actions">
            {history.length > 0 && (
              <button className="clear-history-btn" onClick={onClearHistory}>
                Clear All
              </button>
            )}
            <button className="close-history-btn" onClick={onClose}>
              ✕
            </button>
          </div>
        </div>
        <div className="history-modal-content">
          {history.length === 0 ? (
            <div className="history-empty">
              <p>No extraction history yet</p>
              <p className="history-empty-hint">Extract data from File Upload or API sections to see history</p>
            </div>
          ) : (
            <div className="history-list">
              {history.map((item) => (
                <div key={item.id} className="history-item">
                  <div className="history-item-header" onClick={() => setSelectedItem(selectedItem === item.id ? null : item.id)}>
                    <div className="history-item-info">
                      <span className="history-item-source">{item.source}</span>
                      {item.fileName && (
                        <span className="history-item-name">📄 {item.fileName}</span>
                      )}
                      {item.url && (
                        <span className="history-item-name">🔗 {item.url.length > 50 ? item.url.substring(0, 50) + '...' : item.url}</span>
                      )}
                      <span className="history-item-time">
                        🕒 {new Date(item.timestamp).toLocaleString()}
                      </span>
                      {item.totalRows && (
                        <span className="history-item-rows">📊 {item.totalRows} rows</span>
                      )}
                    </div>
                    <button 
                      className="history-download-btn"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDownload(item)
                      }}
                      title="Download"
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                      </svg>
                    </button>
                  </div>
                  {selectedItem === item.id && (
                    <div className="history-item-details">
                      <div className="history-item-meta">
                        {item.fileType && <span>Type: {item.fileType}</span>}
                        {item.responseFormat && <span>Format: {item.responseFormat}</span>}
                        {item.progress && (
                          <>
                            <span>Extract: {item.progress.extract}s</span>
                            <span>Transform: {item.progress.transform}s</span>
                            <span>Load: {item.progress.load}s</span>
                            <span>Total: {item.progress.total}s</span>
                          </>
                        )}
                        {item.duplicateCount !== undefined && item.duplicateCount > 0 && (
                          <span>Duplicates Removed: {item.duplicateCount}</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default HistoryModal

