import { useEffect, useState } from 'react'
import { api, ApiError, type Plan, type PlatformSubscription } from '../../api'
import { Badge, Card, Icon, PageHeader } from '../../stitch'

export default function Abonnements() {
  const [subs, setSubs] = useState<PlatformSubscription[] | null>(null)
  const [plans, setPlans] = useState<Plan[]>([])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  function load() {
    Promise.all([api.platformSubscriptions(), api.platformPlans()])
      .then(([s, p]) => { setSubs(s.subscriptions); setPlans(p.plans) })
      .catch((e) => setError(e instanceof ApiError ? (e.status === 403 ? 'Accès réservé aux administrateurs plateforme.' : e.message) : 'Erreur réseau'))
  }
  useEffect(load, [])

  async function changePlan(ws: string, plan_code: string) {
    setSaving(ws); setError(null)
    try { await api.setSubscription(ws, plan_code); load() }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Erreur réseau') }
    finally { setSaving(null) }
  }

  return (
    <>
      <PageHeader
        title="Abonnements & facturation"
        subtitle="Plans actifs par espace de travail (cabinet ou entreprise)."
        badge={subs && <Badge tone="neutral">{subs.length} espaces</Badge>}
      />

      {error && <div className="p-4 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold flex items-center gap-2"><Icon name="lock" /> {error}</div>}

      {!error && (subs == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-border text-label-lg font-bold text-muted">
                  <th className="py-3 px-6">Espace de travail</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Statut</th>
                  <th className="py-3 px-6">Plan</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-body-md text-ink">
                {subs.map((s) => (
                  <tr key={s.workspace_id} className="hover:bg-primary-fixed/20 transition-colors">
                    <td className="py-3.5 px-6 font-bold text-ink">{s.workspace}</td>
                    <td className="py-3.5 px-4 text-muted text-label-md">{s.type}</td>
                    <td className="py-3.5 px-4">
                      <Badge tone={s.is_beta ? 'warning' : s.statut === 'active' ? 'success' : 'neutral'}>
                        {s.is_beta ? 'Bêta' : s.statut}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-6">
                      <div className="flex items-center gap-2">
                        <select
                          value={s.plan}
                          disabled={saving === s.workspace_id}
                          onChange={(e) => changePlan(s.workspace_id, e.target.value)}
                          className="px-3 py-1.5 text-label-lg font-semibold bg-white rounded-lg border border-border focus:border-secondary focus:ring-2 focus:ring-secondary/20 outline-none"
                        >
                          {plans.map((p) => <option key={p.code} value={p.code}>{p.libelle}</option>)}
                        </select>
                        {saving === s.workspace_id && <span className="spinner" style={{ width: 16, height: 16 }} />}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
    </>
  )
}
