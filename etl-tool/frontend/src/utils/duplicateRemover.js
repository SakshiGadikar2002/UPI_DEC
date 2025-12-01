/**
 * Remove duplicate objects from an array
 * Uses deep equality comparison by stringifying objects
 */
export const removeDuplicates = (data) => {
  if (!Array.isArray(data)) {
    return { uniqueData: data, duplicateCount: 0 }
  }

  const seen = new Set()
  const uniqueData = []
  let duplicateCount = 0

  for (const item of data) {
    try {
      // Create a normalized string representation
      // Sort keys to ensure consistent comparison
      let normalized
      if (item && typeof item === 'object') {
        const keys = Object.keys(item).sort()
        normalized = JSON.stringify(item, keys)
      } else {
        normalized = JSON.stringify(item)
      }
      
      if (!seen.has(normalized)) {
        seen.add(normalized)
        uniqueData.push(item)
      } else {
        duplicateCount++
      }
    } catch (error) {
      // If serialization fails, treat as unique
      console.warn('Error serializing item for duplicate check:', error)
      uniqueData.push(item)
    }
  }

  return { uniqueData, duplicateCount }
}

