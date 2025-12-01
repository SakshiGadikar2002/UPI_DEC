/**
 * Parse various JSON formats including:
 * - Standard JSON (single object or array)
 * - JSONL/NDJSON (newline-delimited JSON)
 * - Multiple JSON objects in one file
 * - Malformed JSON with multiple objects
 */
export const parseFlexibleJSON = (text) => {
  const trimmedText = text.trim()
  if (!trimmedText) {
    return []
  }

  const results = []
  const errors = []

  // Try standard JSON first
  try {
    const parsed = JSON.parse(trimmedText)
    if (Array.isArray(parsed)) {
      return { data: parsed, errors: [] }
    } else if (typeof parsed === 'object' && parsed !== null) {
      return { data: [parsed], errors: [] }
    } else {
      return { data: [parsed], errors: [] }
    }
  } catch (e) {
    // Not standard JSON, try other formats
  }

  // Try JSONL/NDJSON format (newline-delimited JSON)
  const lines = trimmedText.split('\n').filter(line => line.trim())
  let parsedCount = 0
  let errorCount = 0

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue

    try {
      const parsed = JSON.parse(line)
      results.push(parsed)
      parsedCount++
    } catch (lineError) {
      errorCount++
      errors.push({
        line: i + 1,
        error: lineError.message,
        content: line.substring(0, 100) // First 100 chars
      })
    }
  }

  // If we parsed at least one line successfully, return results
  if (parsedCount > 0) {
    return { data: results, errors }
  }

  // Try parsing multiple JSON objects separated by various delimiters
  // Look for JSON objects in the text
  const jsonObjectRegex = /\{[\s\S]*?\}(?=\s*\{|$)/g
  let match
  const foundObjects = []

  while ((match = jsonObjectRegex.exec(trimmedText)) !== null) {
    try {
      const parsed = JSON.parse(match[0])
      foundObjects.push(parsed)
    } catch (e) {
      // Skip invalid JSON objects
    }
  }

  if (foundObjects.length > 0) {
    return { data: foundObjects, errors }
  }

  // Try to extract JSON from malformed text
  // Look for JSON-like structures
  try {
    // Try to fix common issues: trailing commas, missing quotes, etc.
    let fixedText = trimmedText
    
    // Remove trailing commas before closing braces/brackets
    fixedText = fixedText.replace(/,(\s*[}\]])/g, '$1')
    
    // Try to wrap multiple objects in an array
    if (fixedText.trim().startsWith('{') && !fixedText.trim().startsWith('[{')) {
      // Try to find all objects and wrap them
      const objects = fixedText.match(/\{[^}]*\}/g)
      if (objects && objects.length > 1) {
        try {
          const parsed = JSON.parse('[' + objects.join(',') + ']')
          return { data: parsed, errors }
        } catch (e) {
          // Fall through
        }
      }
    }

    const parsed = JSON.parse(fixedText)
    if (Array.isArray(parsed)) {
      return { data: parsed, errors }
    } else {
      return { data: [parsed], errors }
    }
  } catch (e) {
    // Last resort: return error
    errors.push({
      line: 0,
      error: e.message,
      content: trimmedText.substring(0, 200)
    })
    return { data: [], errors }
  }
}

