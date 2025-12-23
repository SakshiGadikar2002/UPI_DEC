import { useState, useEffect } from 'react'
import './AuthForm.css'
import { getSavedCredentials, isRememberMeEnabled, getLastEmail } from '../utils/credentialStorage'

const AuthForm = ({ loading, error, onLogin, onRegister }) => {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [rememberMe, setRememberMe] = useState(false)

  // Load saved credentials on mount
  useEffect(() => {
    const savedCreds = getSavedCredentials()
    if (savedCreds) {
      // Full credentials available (Remember Me was checked)
      setEmail(savedCreds.email)
      setPassword(savedCreds.password)
      setRememberMe(true)
      console.log('Auto-filled credentials from Remember Me')
    } else {
      // No full credentials, but email should persist per user preference
      const lastEmail = getLastEmail()
      if (lastEmail) {
        setEmail(lastEmail)
        console.log('Auto-filled email from last login')
      }
      // Check if Remember Me flag exists (for preserving checkbox state)
      setRememberMe(isRememberMeEnabled())
    }
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (mode === 'login') {
      await onLogin({ email, password, rememberMe })
    } else {
      await onRegister({ email, password, fullName, rememberMe })
    }
  }

  return (
    <div className="auth-form-wrapper">
      <div className="auth-toggle">
        <button
          className={mode === 'login' ? 'active' : ''}
          onClick={() => setMode('login')}
        >
          Login
        </button>
        <button
          className={mode === 'register' ? 'active' : ''}
          onClick={() => setMode('register')}
        >
          Register
        </button>
      </div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
          />
        </label>

        {mode === 'register' && (
          <label>
            Full name (optional)
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Jane Doe"
            />
          </label>
        )}

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            minLength={6}
          />
        </label>

        {mode === 'login' && (
          <label className="remember-me-label">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
            />
            <span>Remember Me</span>
          </label>
        )}

        {error && <div className="auth-error">{error}</div>}

        <button type="submit" className="auth-submit" disabled={loading}>
          {loading ? 'Please wait...' : mode === 'login' ? 'Login' : 'Register'}
        </button>
      </form>
    </div>
  )
}

export default AuthForm

