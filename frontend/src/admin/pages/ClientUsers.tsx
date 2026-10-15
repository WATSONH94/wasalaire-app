import { useEffect, useMemo, useState } from 'react'
import { api, ApiError, type PlatformUser } from '../../api'
import { Badge, Card, Icon, PageHeader } from '../../stitch'

// Vue d'assistance : utilisateurs des organisations clientes (pouvoirs limités, lecture).
export default function ClientUsers() {
  const [users, setUsers] = useState<PlatformUser[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')

  useEffect(() => {
    api.platformUsers().then((r) => setUsers(r.users)).catch((e) => setError(e instanceof ApiError ? (e.status === 403 ? 'Accès limité.' : e.message) : 'Erreur réseau'))
  }, [])

  const clients = useMemo(() => {
    if (!users) return null
    const base = users.filter((u) => !u.platform_role || u.platform_role === 'none')
    const n = q.trim().toLowerCase()
    return n ? base.filter((u) => (u.email ?? '').toLowerCase().includes(n)) : base
  }, [users, q])

  return (
    <>
      <PageHeader
        title="Utilisateurs clients"
        subtitle="Assistance à la gestion des utilisateurs des organisations clientes (lecture, pouvoirs limités)."
        badge={clients && <Badge tone="neutral">{clients.length}</Badge>}
      />

      <div className="p-3 rounded-xl bg-surface-container-low border border-border text-label-md text-muted flex items-center gap-2">
        <Icon name="info" className="text-[18px]" /> La gestion effective des utilisateurs d’une organisation se fait côté client, par l’admin de l’organisation. Toute intervention sur les données de paie est tracée (break-glass).
      </div>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      <div className="relative max-w-md">
        <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-muted text-[18px]" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher par e-mail…"
          className="w-full pl-9 pr-4 py-2 text-body-md bg-surface border border-border rounded-xl focus:outline-none focus:border-secondary focus:ring-1 focus:ring-secondary" />
      </div>

      {clients == null && !error ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : clients && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-border text-label-lg font-bold text-muted">
                  <th className="py-3 px-6">Utilisateur</th>
                  <th className="py-3 px-4 text-center">MFA</th>
                  <th className="py-3 px-4 text-center">Mot de passe</th>
                  <th className="py-3 px-6">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-body-md text-ink">
                {clients.map((u) => (
                  <tr key={u.id} className="hover:bg-primary-fixed/20 transition-colors">
                    <td className="py-3.5 px-6 font-bold text-ink break-all">{u.email}</td>
                    <td className="py-3.5 px-4 text-center">{u.totp_enrolled ? <Icon name="check_circle" className="text-success" /> : <Icon name="remove_circle" className="text-outline-variant" />}</td>
                    <td className="py-3.5 px-4 text-center">{u.must_change_password ? <Badge tone="warning">À changer</Badge> : <Icon name="check_circle" className="text-success" />}</td>
                    <td className="py-3.5 px-6"><Badge tone={u.statut === 'actif' ? 'success' : 'neutral'}>{u.statut}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  )
}
