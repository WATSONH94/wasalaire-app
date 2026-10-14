import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa } from '../api'
import { Spinner } from '../ui'

// Libellés des agrégats renvoyés par /v1/reporting (reporting_summary).
const LABELS: Record<string, string> = {
  masse_brute: 'Masse brute',
  charges_patronales: 'Charges patronales',
  cout_employeur: 'Coût employeur',
  net_total: 'Net à payer',
  effectif: 'Effectif',
}
// Clés qui sont des comptes (pas des montants) → pas de suffixe FCFA.
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

  if (error) return <div className="error">{error}</div>
  if (!data) return <div className="row"><Spinner /> <span className="muted">Chargement…</span></div>

  const entries = Object.entries(data).filter(([, v]) => typeof v === 'number')
  return (
    <div>
      <h2>Reporting</h2>
      {entries.length === 0 ? (
        <p className="muted">Aucune donnée (aucune paie calculée pour l'instant).</p>
      ) : (
        <div className="list" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))' }}>
          {entries.map(([k, v]) => (
            <div key={k} className="card">
              <div className="muted" style={{ fontSize: '.8rem' }}>{LABELS[k] ?? k}</div>
              <div style={{ fontWeight: 800, fontSize: '1.05rem' }}>
                {COUNTS.has(k) ? v : fcfa(v)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
