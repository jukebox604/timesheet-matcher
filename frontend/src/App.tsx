import { useState, useEffect } from 'react'
import Events from './Events'
import './styles.css'

interface UserInfo {
  sub: string
  email: string
  name: string
  picture: string
}

function parseJwt(token: string): UserInfo | null {
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch {
    return null
  }
}

export default function App() {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<UserInfo | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const urlToken = params.get('token')

    if (urlToken) {
      localStorage.setItem('auth_token', urlToken)
      const parsed = parseJwt(urlToken)
      setUser(parsed)
      setToken(urlToken)
      window.history.replaceState({}, document.title, window.location.pathname)
    } else {
      const storedToken = localStorage.getItem('auth_token')
      if (storedToken) {
        const parsed = parseJwt(storedToken)
        if (parsed) {
          setUser(parsed)
          setToken(storedToken)
        } else {
          localStorage.removeItem('auth_token')
        }
      }
    }
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    setToken(null)
    setUser(null)
  }

  if (token && user) {
    return (
      <div className="app-shell">
        <nav className="nav-bar app-nav-single">
          <div className="nav-brand">Timesheet Matcher</div>
          <button className="logout-btn" onClick={handleLogout}>Logout</button>
        </nav>
        <Events />
      </div>
    )
  }

  return (
    <div className="app-shell">
      <div className="login-container">
        <div className="card login-card">
          <div className="login-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
          </div>
          <h1 className="login-title">Timesheet</h1>
          <p className="login-subtitle">Sign in to get started</p>
          <a
            href="/api/auth/google/login"
            className="google-signin-btn"
          >
            <svg className="google-icon" width="20" height="20" viewBox="0 0 48 48">
              <path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"/>
              <path fill="#FF3D00" d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"/>
              <path fill="#4CAF50" d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"/>
              <path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"/>
            </svg>
            Sign in with Google
          </a>
        </div>
      </div>
    </div>
  )
}