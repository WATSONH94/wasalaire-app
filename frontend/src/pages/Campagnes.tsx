import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, fcfa, type PayrollOverview } from '../api'
import { Badge, Card, Icon } from '../stitch'

const MOIS = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
const STATUT: Record<string, { label: string; tone: 'neutral' | 'warning' | 'secondary' | 'success' }> = {
  aucune: { label: 'Non démarrée', tone: 'neutral' },
  ouverte: { label: 'Ouverte', tone: 'warning' },
  calculee: { label: 'Calculée', tone: 'secondary' },
  validee: { label: 'Validée', tone: 'secondary' },
  cloturee: { label: 'Clôturée', tone: 'success' },
  comptabilisee: { label: 'Comptabilisée', tone: 'success' },
  declaree: { label: 'Déclarée', tone: 'success' },
  payee: { label: 'Payée', tone: 'success' },
}

function Kpi({ label, value, sub, icon }: { label: string; value: string; sub?: string; icon: string }) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between"><span className="text-label-md text-muted">{label}</span><Icon name={icon} className="text-muted" /></div>
      <div className="text-headline-sm font-extrabold text-ink tabular-nums mt-2">{value}</div>
      {sub && <div className="text-label-md text-muted mt-1">{sub}</div>}
    </Card>
  )
}

export default function Campagnes() {
  const now = new Date()
  const [mois, setMois] = useState(now.getMonth() + 1)
  const [annee, setAnnee] = useState(now.getFullYear())
  const [data, setData] = useState<PayrollOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true); setError(null)
    api.payrollOverview(mois, annee).then(setData).catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau')).finally(() => setLoading(false))
  }, [mois, annee])

  const annees = [now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1]

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Paie multi-société</h2>
              <Badge tone="secondary" icon="apartment">Campagne de paie</Badge>
            </div>
            <p className="text-body-md text-muted mt-1 max-w-2xl">Avancement de la paie du mois pour l'ensemble de votre portefeuille : statut, bulletins et net à payer par société.</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <select value={mois} onChange={(e) => setMois(Number(e.target.value))} className="px-3 py-2.5 rounded-xl border border-border bg-white text-ink font-semibold outline-none focus:border-secondary-fixed-dim">
              {MOIS.slice(1).map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
            </select>
            <select value={annee} onChange={(e) => setAnnee(Number(e.target.value))} className="px-3 py-2.5 rounded-xl border border-border bg-white text-ink font-semibold outline-none focus:border-secondary-fixed-dim">
              {annees.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {loading ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : data ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Kpi label="Sociétés" value={String(data.nb_societes)} sub="du portefeuille" icon="apartment" />
            <Kpi label="Paies traitées" value={`${data.nb_traitees} / ${data.nb_societes}`} sub={`${MOIS[mois]} ${annee}`} icon="task_alt" />
            <Kpi label="Bulletins" value={String(data.total_bulletins)} sub="générés" icon="description" />
            <Kpi label="Net à payer global" value={fcfa(data.total_net)} sub="toutes sociétés" icon="payments" />
          </div>

          <Card className="p-0 overflow-hidden">
            <div className="p-5 border-b border-border flex items-center gap-2"><Icon name="list_alt" className="text-muted" /><h3 className="text-subtitle-md font-bold text-ink">Avancement par société — {MOIS[mois]} {annee}</h3></div>
            {data.societes.length === 0 ? (
              <div className="p-10 text-center text-muted"><Icon name="apartment" className="text-[40px] text-outline-variant" /><p className="mt-2">Aucune société dans le portefeuille.</p></div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-body-sm">
                  <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wide">
                    <th className="py-3 px-5">Société</th><th className="py-3 px-3">Statut</th>
                    <th className="py-3 px-3 text-right">Bulletins</th><th className="py-3 px-3 text-right">Net à payer</th>
                    <th className="py-3 px-5 text-right">Action</th>
                  </tr></thead>
                  <tbody className="divide-y divide-border text-ink">
                    {data.societes.map((s) => (
                      <tr key={s.company_id} className="hover:bg-primary-fixed/10">
                        <td className="py-3 px-5 font-bold">{s.raison_sociale}</td>
                        <td className="py-3 px-3"><Badge tone={STATUT[s.statut]?.tone ?? 'neutral'}>{STATUT[s.statut]?.label ?? s.statut}</Badge></td>
                        <td className="py-3 px-3 text-right tabular-nums text-muted">{s.bulletins || '—'}</td>
                        <td className="py-3 px-3 text-right tabular-nums font-bold text-secondary">{s.net ? fcfa(s.net) : '—'}</td>
                        <td className="py-3 px-5 text-right">
                          <Link to={`/c/${s.company_id}/paie`} className="inline-flex items-center gap-1 px-3 py-1.5 bg-secondary-fixed text-ink font-bold text-label-md rounded-lg hover:bg-secondary-fixed-dim">
                            <Icon name="arrow_forward" className="text-[16px]" /> {s.statut === 'aucune' || s.statut === 'ouverte' ? 'Traiter' : 'Ouvrir'}
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot><tr className="bg-primary/5 border-t-2 border-primary font-extrabold text-ink">
                    <td className="py-3 px-5" colSpan={2}>TOTAL ({data.nb_traitees}/{data.nb_societes} traitées)</td>
                    <td className="py-3 px-3 text-right tabular-nums">{data.total_bulletins}</td>
                    <td className="py-3 px-3 text-right tabular-nums text-secondary">{fcfa(data.total_net)}</td>
                    <td className="py-3 px-5"></td>
                  </tr></tfoot>
                </table>
              </div>
            )}
            <p className="p-4 text-label-md text-muted flex items-start gap-1.5"><Icon name="info" className="text-[16px] mt-0.5" />Vue consolidée du portefeuille. Chaque société se traite dans son propre cycle de paie (bouton « Traiter / Ouvrir »).</p>
          </Card>
        </>
      ) : null}
    </div>
  )
}
