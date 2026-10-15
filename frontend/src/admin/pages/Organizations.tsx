import { useEffect, useMemo, useState } from 'react'
import { api, ApiError, type AdminOrg } from '../../api'
import { Badge, Card, Icon, PageHeader } from '../../stitch'

const TYPE_LABEL: Record<string, string> = {
  cabinet_comptable: 'Cabinet comptable',
  entreprise_directe: 'Entreprise',
  groupe: 'Groupe',
}

export default function Organizations() {
  const [orgs, setOrgs] = useState<AdminOrg[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')

  useEffect(() => {
    api.adminOrganizations().then((r) => setOrgs(r.organizations)).catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }, [])

  const filtered = useMemo(() => {
    if (!orgs) return null
    const n = q.trim().toLowerCase()
    return n ? orgs.filter((o) => o.nom.toLowerCase().includes(n)) : orgs
  }, [orgs, q])

  return (
    <>
      <PageHeader
        title="Organisations clientes"
        subtitle="Cabinets, groupes et entreprises abonnés à WaSalaire."
        badge={orgs && <Badge tone="neutral">{orgs.length}</Badge>}
      />

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      <div className="relative max-w-md">
        <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-muted text-[18px]" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher une organisation…"
          className="w-full pl-9 pr-4 py-2 text-body-md bg-surface border border-border rounded-xl focus:outline-none focus:border-secondary focus:ring-1 focus:ring-secondary" />
      </div>

      {filtered == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-border text-label-lg font-bold text-muted">
                  <th className="py-3 px-6">Organisation</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4 text-center">Sociétés</th>
                  <th className="py-3 px-4">Plan</th>
                  <th className="py-3 px-6">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-body-md text-ink">
                {filtered.map((o) => (
                  <tr key={o.id} className="hover:bg-primary-fixed/20 transition-colors">
                    <td className="py-3.5 px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">{o.nom.slice(0, 2).toUpperCase()}</div>
                        <span className="font-bold text-ink">{o.nom}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-muted text-label-md">{TYPE_LABEL[o.type] ?? o.type}</td>
                    <td className="py-3.5 px-4 text-center font-semibold tabular-nums">{o.nb_companies}</td>
                    <td className="py-3.5 px-4">{o.plan ? <Badge tone="secondary">{o.plan}</Badge> : <span className="text-muted text-label-md">—</span>}</td>
                    <td className="py-3.5 px-6">
                      {o.statut ? <Badge tone={o.is_beta ? 'warning' : o.statut === 'active' ? 'success' : 'neutral'}>{o.is_beta ? 'Bêta' : o.statut}</Badge>
                        : <Badge tone="neutral">Sans abonnement</Badge>}
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
