import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, getToken, setToken, type Session } from './api'

interface AuthState {
  session: Session | null
  loading: boolean
  login: (s: Session) => void
  logout: () => void
}

const AuthContext = createContext<AuthState | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  // Un jeton présent est revalidé auprès de l'API (révocation immédiate côté serveur).
  useEffect(() => {
    const t = getToken()
    if (!t) { setLoading(false); return }
    api.me()
      .then((me) => setSession({ token: t, user_id: me.user_id, companies: me.companies, roles: me.roles, email: me.email, platform_role: me.platform_role, mfa_enrolled: me.mfa_enrolled }))
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  const login = (s: Session) => {
    setToken(s.token); setSession(s)
    // Enrichit la session (email, rôle plateforme, statut MFA) sans bloquer.
    api.me()
      .then((m) => setSession({ ...s, email: m.email, platform_role: m.platform_role, mfa_enrolled: m.mfa_enrolled }))
      .catch(() => { /* la session de base reste valable */ })
  }
  const logout = () => { setToken(null); setSession(null) }

  return <AuthContext.Provider value={{ session, loading, login, logout }}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé dans AuthProvider')
  return ctx
}
