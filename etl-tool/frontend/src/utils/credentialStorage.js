/**
 * Secure credential storage utility for Remember Me functionality
 * Uses base64 encoding (not true encryption, but obfuscation for localStorage)
 * 
 * IMPORTANT: This is client-side storage. For production, consider:
 * - Using HTTP-only cookies with secure flags
 * - Implementing proper encryption with Web Crypto API
 * - Server-side session management
 */

const STORAGE_KEY = 'etl-remember-me'
const CREDENTIALS_KEY = 'etl-saved-creds'
const EMAIL_KEY = 'etl-last-email' // Store email separately for persistence

/**
 * Simple obfuscation function (base64 encoding)
 * NOTE: This is NOT real encryption - it's just to prevent casual viewing
 */
const encode = (str) => {
  try {
    return btoa(unescape(encodeURIComponent(str)))
  } catch (e) {
    console.error('Encoding error:', e)
    return null
  }
}

const decode = (str) => {
  try {
    return decodeURIComponent(escape(atob(str)))
  } catch (e) {
    console.error('Decoding error:', e)
    return null
  }
}

/**
 * Save credentials when Remember Me is checked
 * @param {string} email - User email
 * @param {string} password - User password
 */
export const saveCredentials = (email, password) => {
  try {
    const credentials = {
      email: encode(email),
      password: encode(password),
      timestamp: new Date().toISOString()
    }
    localStorage.setItem(CREDENTIALS_KEY, JSON.stringify(credentials))
    localStorage.setItem(STORAGE_KEY, 'true')
    // Always save email separately for persistence after logout
    localStorage.setItem(EMAIL_KEY, email)
    console.log('✅ Credentials saved (Remember Me enabled)')
  } catch (e) {
    console.error('Failed to save credentials:', e)
  }
}

/**
 * Get saved credentials if Remember Me was enabled
 * @returns {{email: string, password: string} | null}
 */
export const getSavedCredentials = () => {
  try {
    const rememberMe = localStorage.getItem(STORAGE_KEY)
    if (rememberMe !== 'true') {
      return null
    }

    const stored = localStorage.getItem(CREDENTIALS_KEY)
    if (!stored) {
      return null
    }

    const credentials = JSON.parse(stored)
    const email = decode(credentials.email)
    const password = decode(credentials.password)

    if (!email || !password) {
      console.warn('Invalid stored credentials, clearing...')
      clearCredentials()
      return null
    }

    console.log('✅ Retrieved saved credentials')
    return { email, password }
  } catch (e) {
    console.error('Failed to retrieve credentials:', e)
    clearCredentials()
    return null
  }
}

/**
 * Clear saved credentials (called on logout when Remember Me is disabled)
 * NOTE: Email is preserved for user convenience (per user preference)
 */
export const clearCredentials = () => {
  try {
    localStorage.removeItem(CREDENTIALS_KEY)
    localStorage.removeItem(STORAGE_KEY)
    // Keep email for next login (user preference)
    console.log('✅ Credentials cleared (email preserved)')
  } catch (e) {
    console.error('Failed to clear credentials:', e)
  }
}

/**
 * Check if Remember Me is currently enabled
 * @returns {boolean}
 */
export const isRememberMeEnabled = () => {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'true'
  } catch (e) {
    return false
  }
}

/**
 * Update only the Remember Me flag without changing credentials
 * @param {boolean} enabled
 */
export const setRememberMeFlag = (enabled) => {
  try {
    if (enabled) {
      localStorage.setItem(STORAGE_KEY, 'true')
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch (e) {
    console.error('Failed to set Remember Me flag:', e)
  }
}

/**
 * Get the last used email (always persists for user convenience)
 * @returns {string | null}
 */
export const getLastEmail = () => {
  try {
    return localStorage.getItem(EMAIL_KEY)
  } catch (e) {
    return null
  }
}

/**
 * Save email for persistence (called on every login)
 * @param {string} email
 */
export const saveEmail = (email) => {
  try {
    localStorage.setItem(EMAIL_KEY, email)
  } catch (e) {
    console.error('Failed to save email:', e)
  }
}
