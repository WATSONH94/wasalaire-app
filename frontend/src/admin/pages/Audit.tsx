import { useEffect, useState } from 'react'
import { api, ApiError, type AuditEvent } from '../../api'
import { Badge, Card, Icon, PageHeader } from '../../stitch'

const TONE: Record<string, 'danger' | 'warning' | 'success' | 'primary' | 'neutral'> = {
  breakglass_grant: 'warning', platform_role_changed: 'primary', lockout: 'danger',
  login_fail: 'danger', login_ok: 'success', mfa_ok: 'success', totp_enrolled: 'success',
  subscription_changed: 'primary',
}
const LABEL: Record<string, string> = {
  breakglass_grant: 'Accès transverse (break-glass)', platform_role_changed: 'Changement de rôle interne',
  lockout: 'Verrouillage', login_fail: 'Échec de connexion', login_ok: 'Connexion', mfa_ok: 'MFA validée',
  totp_enrolled: 'MFA activée', subscription_changed: 'Abonnement modifié', password_changed: 'Mot de passe changé',
}

export default function Audit() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.adminAudit(200).then((r) => setEvents(r.events)).catch((e) => setError(e instanceof ApiError ? (e.status === 403 ? 'Réservé aux administrateurs plateforme.' : e.message) : 'Erreur réseau'))
  }, [])

  return (
    <>
      <PageHeader title="Audit & sécurité" subtitle="Journal des événements sensibles (lecture seule, protégé)." badge={events && <Badge tone="neutral">{events.length}</Badge>} />

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold flex items-center gap-2"><Icon name="lock" /> {error}</div>}

      {events == null && !error ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : events && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-border text-label-lg font-bold text-muted">
                  <th className="py-3 px-6">Horodatage</th>
                  <th className="py-3 px-4">Événement</th>
                  <th className="py-3 px-4">Utilisateur</th>
                  <th className="py-3 px-4">IP</th>
                  <th className="py-3 px-6">Détail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-body-md text-ink">
                {events.map((e) => (
                  <tr key={e.id} className="hover:bg-primary-fixed/20 transition-colors">
                    <td className="py-3 px-6 text-label-md text-muted tabular-nums whitespace-nowrap">{e.created_at ? new Date(e.created_at).toLocaleString('fr-FR') : '—'}</td>
                    <td className="py-3 px-4"><Badge tone={TONE[e.type] ?? 'neutral'}>{LABEL[e.type] ?? e.type}</Badge></td>
                    <td className="py-3 px-4 text-label-md text-muted break-all">{e.email ?? (e.user_id ? e.user_id.slice(0, 8) + '…' : '—')}</td>
                    <td className="py-3 px-4 text-label-md text-muted font-mono">{e.ip ?? '—'}</td>
                    <td className="py-3 px-6 text-label-md text-muted font-mono max-w-xs truncate">{e.detail ? JSON.stringify(e.detail) : ''}</td>
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
