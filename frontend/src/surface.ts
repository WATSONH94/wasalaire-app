// Détermine la surface servie : back-office ADMIN interne vs application CLIENT.
// Prod : par sous-domaine (admin.wasalaire…). Dev local : ?surface=admin (persistant).
export function isAdminSurface(): boolean {
  try {
    const host = location.hostname
    if (host.startsWith('admin.')) return true
    const q = new URLSearchParams(location.search).get('surface')
    if (q === 'admin') { try { localStorage.setItem('wasalaire.surface', 'admin') } catch { /* noop */ } return true }
    if (q === 'client') { try { localStorage.removeItem('wasalaire.surface') } catch { /* noop */ } return false }
    const local = host === 'localhost' || host === '127.0.0.1'
    return local && (() => { try { return localStorage.getItem('wasalaire.surface') === 'admin' } catch { return false } })()
  } catch {
    return false
  }
}
