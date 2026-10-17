import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Reconciliation, type Run } from '../api'
import { Badge, Card, Icon } from '../stitch'

const MOIS = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

export default function Rapprochement() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [sel, setSel] = useState<Run | null>(null)
  const [rec, setRec] = useState<Reconciliation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.companyRuns(cid)
      .then((r) => {
        const closed = r.runs.filter((x) => x.actif !== false && x.statut === 'cloturee')
        setRuns(closed)
        if (closed[0]) setSel(closed[0])
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }, [cid])

  useEffect(() => {
    if (!sel) { setRec(null); return }
    setLoading(true); setRec(null); setError(null)
    api.reconciliation(sel.run_id)
      .then(setRec)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
      .finally(() => setLoading(false))
  }, [sel])

  const periode = rec ? `${MOIS[rec.periode.mois]} ${rec.periode.annee}` : ''

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Rapprochement paie ↔ comptabilité</h2>
          <Badge tone="secondary" icon="fact_check">Contrôle de cohérence</Badge>
        </div>
        <p className="text-body-md text-muted mt-1 max-w-2xl">Confronte les agrégats de paie (bulletins) au journal SYSCOHADA généré. Tout écart signale une incohérence à corriger avant déclaration.</p>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {runs == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : runs.length === 0 ? (
        <Card className="p-10 text-center"><Icon name="fact_check" className="text-[40px] text-outline-variant" /><p className="text-muted mt-2">Aucun cycle clôturé. Le rapprochement s'effectue sur une paie clôturée (écriture comptable générée).</p></Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
          <Card className="p-3 lg:col-span-1 h-fit">
            <div className="text-label-md font-bold text-muted uppercase px-2 py-1">Cycles clôturés</div>
            <div className="flex flex-col gap-1">
              {runs.map((r) => (
                <button key={r.run_id} onClick={() => setSel(r)}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-colors ${sel?.run_id === r.run_id ? 'bg-secondary/10 text-secondary' : 'hover:bg-surface-container-low text-ink'}`}>
                  <span className="font-bold capitalize">{MOIS[r.mois]} {r.annee}</span>
                  <Icon name="chevron_right" className="text-muted" />
                </button>
              ))}
            </div>
          </Card>

          <div className="lg:col-span-3 flex flex-col gap-5">
            {loading ? (
              <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Contrôle en cours…</div>
            ) : !rec ? (
              <Card className="p-8 text-center text-muted">Sélectionnez un cycle clôturé.</Card>
            ) : (
              <>
                <div className={`p-4 rounded-2xl border flex items-center gap-3 ${rec.concordant ? 'bg-success/10 border-success/30' : 'bg-danger/10 border-danger/30'}`}>
                  <Icon name={rec.concordant ? 'verified' : 'error'} className={`text-[28px] ${rec.concordant ? 'text-success' : 'text-danger'}`} />
                  <div>
                    <div className="font-extrabold text-ink">{rec.concordant ? 'Paie et comptabilité concordantes' : `${rec.ecarts} écart(s) détecté(s)`}</div>
                    <div className="text-label-md text-muted">{periode} · Journal {rec.equilibre ? 'équilibré' : 'déséquilibré'} (débit {fcfa(rec.total_debit)} / crédit {fcfa(rec.total_credit)})</div>
                  </div>
                </div>

                <Card className="p-0 overflow-hidden">
                  <div className="p-5 border-b border-border flex items-center gap-2"><Icon name="balance" className="text-muted" /><h3 className="text-subtitle-md font-bold text-ink">Points de contrôle — {periode}</h3></div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-body-sm">
                      <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wide">
                        <th className="py-3 px-5">Poste</th><th className="py-3 px-3 text-right">Côté paie</th>
                        <th className="py-3 px-3 text-right">Côté compta</th><th className="py-3 px-3 text-right">Écart</th>
                        <th className="py-3 px-4 text-center">Contrôle</th>
                      </tr></thead>
                      <tbody className="divide-y divide-border text-ink">
                        {rec.lignes.map((l, i) => (
                          <tr key={i} className={l.ok ? 'hover:bg-primary-fixed/10' : 'bg-danger/5'}>
                            <td className="py-3 px-5 font-semibold">{l.libelle}</td>
                            <td className="py-3 px-3 text-right tabular-nums">{fcfa(l.paie)}</td>
                            <td className="py-3 px-3 text-right tabular-nums">{fcfa(l.compta)}</td>
                            <td className={`py-3 px-3 text-right tabular-nums font-semibold ${l.ecart ? 'text-danger' : 'text-muted'}`}>{l.ecart ? fcfa(l.ecart) : '0'}</td>
                            <td className="py-3 px-4 text-center">
                              {l.ok ? <Icon name="check_circle" className="text-success" /> : <Icon name="cancel" className="text-danger" />}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="p-4 text-label-md text-muted flex items-start gap-1.5"><Icon name="info" className="text-[16px] mt-0.5" />Les deux colonnes dérivent des mêmes bulletins ; un écart non nul révèle une anomalie de génération (à investiguer avant tout dépôt DGI/CNSS).</p>
                </Card>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
