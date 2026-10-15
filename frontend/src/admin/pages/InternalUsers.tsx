import { useEffect, useState } from 'react'
import { api, ApiError, type PlatformUser } from '../../api'
import { Badge, Card, Icon, PageHeader } from '../../stitch'
import { useAuth } from '../../auth'

const ROLES = [
  { code: 'super_admin', label: 'Super-administrateur' },
  { code: 'admin_plateforme', label: 'Admin plateforme' },
  { code: 'support', label: 'Support technique' },
  { code: 'conformite', label: 'Responsable conformité' },
  { code: 'commercial', label: 'Responsable commercial' },
  { code: 'none', label: 'Retirer (utilisateur client)' },
]

export default function InternalUsers() {
  const { session } = useAuth()
  const canManage = session?.platform_role === 'super_admin'
  const [users, setUsers] = useState<PlatformUser[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  function load() {
    api.adminInternalUsers().then((r) => setUsers(r.users)).catch((e) => setError(e instanceof ApiError ? (e.status === 403 ? "Réservé aux administrateurs plateforme." : e.message) : 'Erreur réseau'))
  }
  useEffect(load, [])

  async function changeRole(id: string, role: string) {
    setSaving(id); setError(null)
    try { await api.adminSetRole(id, role); load() }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Erreur réseau') }
    finally { setSaving(null) }
  }

  return (
    <>
      <PageHeader
        title="Utilisateurs internes WaSalaire"
        subtitle="Collaborateurs de l’éditeur et leurs rôles internes. Distinct des utilisateurs clients."
        badge={users && <Badge tone="neutral">{users.length}</Badge>}
      />

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}
      {!canManage && users && (
        <div className="p-3 rounded-xl bg-surface-container-low border border-border text-label-md text-muted flex items-center gap-2">
          <Icon name="info" className="text-[18px]" /> La modification des rôles internes est réservée au super-administrateur.
        </div>
      )}

      {users == null && !error ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : users && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-border text-label-lg font-bold text-muted">
                  <th className="py-3 px-6">Collaborateur</th>
                  <th className="py-3 px-4 text-center">MFA</th>
                  <th className="py-3 px-4">Statut</th>
                  <th className="py-3 px-6">Rôle interne</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-body-md text-ink">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-primary-fixed/20 transition-colors">
                    <td className="py-3.5 px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-ink/10 text-ink flex items-center justify-center font-bold text-xs">{(u.email ?? '?').slice(0, 2).toUpperCase()}</div>
                        <span className="font-bold text-ink break-all">{u.email}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-center">{u.totp_enrolled ? <Icon name="check_circle" className="text-success" /> : <Icon name="remove_circle" className="text-outline-variant" />}</td>
                    <td className="py-3.5 px-4"><Badge tone={u.statut === 'actif' ? 'success' : 'neutral'}>{u.statut}</Badge></td>
                    <td className="py-3.5 px-6">
                      {canManage ? (
                        <div className="flex items-center gap-2">
                          <select value={u.platform_role ?? 'none'} disabled={saving === u.id}
                            onChange={(e) => changeRole(u.id, e.target.value)}
                            className="px-3 py-1.5 text-label-lg font-semibold bg-white rounded-lg border border-border focus:border-secondary focus:ring-2 focus:ring-secondary/20 outline-none">
                            {ROLES.map((r) => <option key={r.code} value={r.code}>{r.label}</option>)}
                          </select>
                          {saving === u.id && <span className="spinner" style={{ width: 16, height: 16 }} />}
                        </div>
                      ) : <Badge tone="primary" icon="shield">{ROLES.find((r) => r.code === u.platform_role)?.label ?? u.platform_role}</Badge>}
                    </td>
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
