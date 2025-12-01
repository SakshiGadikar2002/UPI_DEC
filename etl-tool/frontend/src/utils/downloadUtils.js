/**
 * Download data as CSV file
 */
export const downloadCSV = (data, filename = 'data.csv') => {
  if (!Array.isArray(data) || data.length === 0) {
    console.error('Data must be a non-empty array')
    return
  }

  // Get all unique keys from all objects
  const allKeys = new Set()
  data.forEach(item => {
    if (typeof item === 'object' && item !== null) {
      Object.keys(item).forEach(key => allKeys.add(key))
    }
  })

  const headers = Array.from(allKeys)
  
  // Create CSV content
  let csvContent = headers.join(',') + '\n'
  
  data.forEach(item => {
    const row = headers.map(header => {
      const value = item[header]
      if (value === null || value === undefined) {
        return ''
      }
      // Escape commas and quotes in CSV
      const stringValue = String(value)
      if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
        return `"${stringValue.replace(/"/g, '""')}"`
      }
      return stringValue
    })
    csvContent += row.join(',') + '\n'
  })

  // Create blob and download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

/**
 * Download data as JSON file
 */
export const downloadJSON = (data, filename = 'data.json') => {
  const jsonContent = JSON.stringify(data, null, 2)
  const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

