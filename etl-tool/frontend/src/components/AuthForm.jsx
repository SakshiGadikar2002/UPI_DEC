import { useState } from 'react'
import './AuthForm.css'

const AuthForm = ({ loading, error, onLogin, onRegister }) => {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (mode === 'login') {
      await onLogin({ email, password })
    } else {
      await onRegister({ email, password, fullName })
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

        {error && <div className="auth-error">{error}</div>}

        <button type="submit" className="auth-submit" disabled={loading}>
          {loading ? 'Please wait...' : mode === 'login' ? 'Login' : 'Register'}
        </button>
      </form>
    </div>
  )
}

export default AuthForm

