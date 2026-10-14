import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa } from '../api'
import { Card, Icon, StatCard } from '../stitch'

// Libellés des agrégats renvoyés par /v1/reporting (reporting_summary).
const LABELS: Record<string, string> = {
  masse_brute: 'Masse brute',
  charges_patronales: 'Charges patronales',
  cout_employeur: 'Coût employeur',
  net_total: 'Net à payer',
  effectif: 'Effectif',
}
const ICONS: Record<string, string> = {
  masse_brute: 'payments',
  charges_patronales: 'account_balance',
  cout_employeur: 'savings',
  net_total: 'wallet',
  effectif: 'badge',
}
const COUNTS = new Set(['effectif'])

export default function Reporting() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [data, setData] = useState<Record<string, number> | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.reporting(cid)
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }, [cid])

  const entries = data ? Object.entries(data).filter(([, v]) => typeof v === 'number') : []

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-subtitle-lg font-subtitle-lg text-ink">Reporting</h2>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {data == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : entries.length === 0 ? (
        <Card className="p-10 text-center">
          <Icon name="bar_chart" className="text-[40px] text-outline-variant" />
          <p className="text-muted mt-2">Aucune donnée : aucune paie calculée pour l’instant.</p>
        </Card>
      ) : (
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {entries.map(([k, v]) => (
            <StatCard
              key={k}
              label={LABELS[k] ?? k}
              value={COUNTS.has(k) ? v : fcfa(v).replace(' FCFA', '')}
              unit={COUNTS.has(k) ? undefined : 'FCFA'}
              icon={ICONS[k] ?? 'analytics'}
            />
          ))}
        </section>
      )}
    </div>
  )
}
