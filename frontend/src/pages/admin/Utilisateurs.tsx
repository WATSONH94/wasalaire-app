import { useEffect, useState } from 'react'
import { api, ApiError, type PlatformUser } from '../../api'
import { Badge, Card, Icon, PageHeader } from '../../stitch'

const ROLE: Record<string, { label: string; tone: 'primary' | 'secondary' | 'neutral' }> = {
  super_admin: { label: 'Super-admin', tone: 'primary' },
  admin_plateforme: { label: 'Admin plateforme', tone: 'secondary' },
}

export default function Utilisateurs() {
  const [users, setUsers] = useState<PlatformUser[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.platformUsers()
      .then((r) => setUsers(r.users))
      .catch((e) => setError(e instanceof ApiError ? (e.status === 403 ? "Accès réservé aux administrateurs plateforme." : e.message) : 'Erreur réseau'))
  }, [])

  return (
    <>
      <PageHeader
        title="Utilisateurs & droits d’accès"
        subtitle="Comptes de la plateforme, rôles transverses et statut de sécurité."
        badge={users && <Badge tone="neutral">{users.length} comptes</Badge>}
      />

      {error && <div className="p-4 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold flex items-center gap-2"><Icon name="lock" /> {error}</div>}

      {!error && (users == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-border text-label-lg font-bold text-muted">
                  <th className="py-3 px-6">Utilisateur</th>
                  <th className="py-3 px-4">Rôle plateforme</th>
                  <th className="py-3 px-4 text-center">MFA</th>
                  <th className="py-3 px-4 text-center">Mot de passe</th>
                  <th className="py-3 px-6">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-body-md text-ink">
                {users.map((u) => {
                  const role = u.platform_role && u.platform_role !== 'none' ? ROLE[u.platform_role] : null
                  return (
                    <tr key={u.id} className="hover:bg-primary-fixed/20 transition-colors">
                      <td className="py-3.5 px-6">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">
                            {(u.email ?? '?').slice(0, 2).toUpperCase()}
                          </div>
                          <span className="font-bold text-ink break-all">{u.email}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        {role ? <Badge tone={role.tone} icon="shield">{role.label}</Badge> : <span className="text-muted text-label-md">Utilisateur</span>}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        {u.totp_enrolled
                          ? <Icon name="check_circle" className="text-success" />
                          : <Icon name="remove_circle" className="text-outline-variant" />}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        {u.must_change_password
                          ? <Badge tone="warning">À changer</Badge>
                          : <Icon name="check_circle" className="text-success" />}
                      </td>
                      <td className="py-3.5 px-6">
                        <Badge tone={u.statut === 'actif' ? 'success' : 'neutral'}>{u.statut}</Badge>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
    </>
  )
}
