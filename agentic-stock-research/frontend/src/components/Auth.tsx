import React, { useState, useEffect, createContext, useContext } from 'react';

interface User {
  id: string; email: string; username: string; full_name: string;
  created_at: string; last_login?: string; is_premium: boolean;
}

interface AuthContextType {
  user: User | null; token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, fullName: string, password: string) => Promise<void>;
  logout: () => void; loading: boolean; error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const authFetch = async (url: string, body: object) => {
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || `${url} failed`)
  return data
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const applyAuth = (token: string, user: User) => {
    setToken(token); setUser(user); localStorage.setItem('auth_token', token)
  }
  const clearAuth = () => {
    setUser(null); setToken(null); localStorage.removeItem('auth_token'); setError(null)
  }

  useEffect(() => {
    const storedToken = localStorage.getItem('auth_token')
    if (!storedToken) { setLoading(false); return }
    setToken(storedToken)
    fetch('/auth/me', { headers: { 'Authorization': `Bearer ${storedToken}`, 'Content-Type': 'application/json' } })
      .then(res => res.ok ? res.json() : Promise.reject())
      .then(setUser)
      .catch(clearAuth)
      .finally(() => setLoading(false))
  }, [])

  const withLoading = async (fn: () => Promise<void>) => {
    setLoading(true); setError(null)
    try { await fn() } catch (err) { setError(err instanceof Error ? err.message : 'Failed'); throw err }
    finally { setLoading(false) }
  }

  const login = (email: string, password: string) =>
    withLoading(async () => { const d = await authFetch('/auth/login', { email, password }); applyAuth(d.access_token, d.user) })

  const register = (email: string, username: string, fullName: string, password: string) =>
    withLoading(async () => { const d = await authFetch('/auth/register', { email, username, full_name: fullName, password }); applyAuth(d.access_token, d.user) })

  return <AuthContext.Provider value={{ user, token, login, register, logout: clearAuth, loading, error }}>{children}</AuthContext.Provider>
}

export const useAuth = (): AuthContextType => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}

export const LoginForm: React.FC = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isLogin, setIsLogin] = useState(true)
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const { login, register, loading, error } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try { isLogin ? await login(email, password) : await register(email, username, fullName, password) } catch {}
  }

  const inputCls = "mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
  const Field = ({ id, label, type = 'text', value, onChange, placeholder }: any) => (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700">{label}</label>
      <input id={id} name={id} type={type} required value={value} onChange={(e: any) => onChange(e.target.value)} className={inputCls} placeholder={placeholder} />
    </div>
  )

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            {isLogin ? 'Sign in to your account' : 'Create your account'}
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Or{' '}
            <button onClick={() => setIsLogin(!isLogin)} className="font-medium text-blue-600 hover:text-blue-500">
              {isLogin ? 'create a new account' : 'sign in to existing account'}
            </button>
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-md">{error}</div>}
          <div className="space-y-4">
            {!isLogin && <>
              <Field id="fullName" label="Full Name" value={fullName} onChange={setFullName} placeholder="Enter your full name" />
              <Field id="username" label="Username" value={username} onChange={setUsername} placeholder="Choose a username" />
            </>}
            <Field id="email" label={isLogin ? 'Email or Username' : 'Email Address'} type={isLogin ? 'text' : 'email'} value={email} onChange={setEmail} placeholder={isLogin ? 'Enter your email or username' : 'Enter your email'} />
            <Field id="password" label="Password" type="password" value={password} onChange={setPassword} placeholder="Enter your password" />
          </div>
          <button type="submit" disabled={loading}
            className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed">
            {loading
              ? <div className="flex items-center"><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />{isLogin ? 'Signing in...' : 'Creating account...'}</div>
              : isLogin ? 'Sign in' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  )
}

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500" /></div>
  if (!user) return <LoginForm />
  return <>{children}</>
}

export const UserProfile: React.FC = () => {
  const { user, logout } = useAuth()
  const [preferences, setPreferences] = useState<any>(null)
  const [watchlist, setWatchlist] = useState<string[]>([])

  useEffect(() => {
    if (!user) return
    Promise.all([fetch('/auth/preferences'), fetch('/auth/watchlist')]).then(async ([prefsRes, watchRes]) => {
      if (prefsRes.ok) setPreferences(await prefsRes.json())
      if (watchRes.ok) setWatchlist((await watchRes.json()).watchlist || [])
    }).catch(console.error)
  }, [user])

  if (!user) return null

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{user.full_name}</h2>
          <p className="text-gray-600">@{user.username}</p>
          <p className="text-sm text-gray-500">{user.email}</p>
        </div>
        <button onClick={logout} className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors">Logout</button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h3 className="text-lg font-semibold mb-3">Preferences</h3>
          {preferences && (
            <div className="space-y-2 text-sm">
              <div><span className="font-medium">Country:</span> {preferences.default_country}</div>
              <div><span className="font-medium">Timeframe:</span> {preferences.default_timeframe}</div>
              <div><span className="font-medium">Theme:</span> {preferences.chart_theme}</div>
              <div><span className="font-medium">Risk Tolerance:</span> {preferences.risk_tolerance}</div>
            </div>
          )}
        </div>
        <div>
          <h3 className="text-lg font-semibold mb-3">Watchlist ({watchlist.length})</h3>
          <div className="space-y-1">
            {watchlist.length > 0
              ? watchlist.map(t => <div key={t} className="text-sm text-gray-700">{t}</div>)
              : <p className="text-sm text-gray-500">No stocks in watchlist</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
