import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Employee, type Period, type VariableRow } from '../api'
import { Badge, Card, Icon } from '../stitch'

const MOIS = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

export default function Avances() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [open, setOpen] = useState<Period | null | undefined>(undefined)   // undefined = chargement
  const [emps, setEmps] = useState<Employee[]>([])
  const [list, setList] = useState<VariableRow[] | null>(null)
  const [form, setForm] = useState({ employee_id: '', montant: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const msg = (e: unknown) => (e instanceof ApiError ? e.message : 'Erreur réseau')

  useEffect(() => {
    api.periods(cid)
      .then((r) => setOpen(r.periods.find((p) => p.statut === 'ouverte') ?? null))
      .catch((e) => { setError(msg(e)); setOpen(null) })
    api.employees(cid).then((r) => setEmps(r.employes)).catch(() => undefined)
  }, [cid])

  const reload = (pid: string) => api.periodVariables(pid, 'avance').then((r) => setList(r.variables)).catch(() => setList([]))
  useEffect(() => { if (open?.period_id) reload(open.period_id) }, [open])

  const montant = parseFloat(form.montant)
  const canSubmit = open?.period_id && form.employee_id && montant > 0

  const enregistrer = () => {
    if (!canSubmit || !open?.period_id) return
    setBusy(true); setError(null)
    api.addVariable({ company_id: cid, period_id: open.period_id, employee_id: form.employee_id, type: 'avance', montant })
      .then(() => { setForm({ employee_id: '', montant: '' }); return reload(open.period_id!) })
      .catch((e) => setError(msg(e)))
      .finally(() => setBusy(false))
  }

  const champ = 'w-full px-3 py-2.5 rounded-xl border border-border bg-white text-ink outline-none focus:border-secondary-fixed-dim focus:ring-2 focus:ring-secondary-fixed-dim/30'
  const total = (list ?? []).reduce((s, v) => s + v.montant, 0)

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Avances &amp; acomptes</h2>
          <Badge tone="secondary" icon="payments">Prélevé sur le net</Badge>
        </div>
        <p className="text-body-md text-muted mt-1 max-w-2xl">Enregistrez les avances sur salaire du mois : elles sont automatiquement <span className="font-semibold text-ink">retenues sur le net à payer</span> du bulletin (après impôts et cotisations).</p>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {open === undefined ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : open === null ? (
        <Card className="p-10 text-center">
          <Icon name="event_busy" className="text-[40px] text-outline-variant" />
          <p className="text-muted mt-2">Aucune période de paie ouverte. Ouvrez la période du mois pour enregistrer des avances.</p>
          <Link to={`/c/${cid}/paie`} className="inline-flex items-center gap-1.5 px-4 py-2.5 mt-4 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container shadow-sm"><Icon name="event_available" className="text-[18px]" /> Aller au cycle de paie</Link>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <Card className="p-5 lg:col-span-1 h-fit flex flex-col gap-3">
            <div className="flex items-center gap-2"><Icon name="add_card" className="text-secondary" /><h3 className="text-subtitle-md font-bold text-ink">Nouvelle avance</h3></div>
            <div className="text-label-md text-muted">Période ouverte : <span className="font-bold text-ink capitalize">{MOIS[open.mois]} {open.annee}</span></div>
            <div><span className="block text-label-md font-semibold text-ink mb-1">Salarié</span>
              <select className={champ} value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })}>
                <option value="">— Sélectionner —</option>
                {emps.map((e) => <option key={e.id} value={e.id}>{e.nom} ({e.matricule})</option>)}
              </select>
            </div>
            <div><span className="block text-label-md font-semibold text-ink mb-1">Montant de l'avance</span>
              <div className="relative">
                <input type="number" min={0} className={champ} value={form.montant} onChange={(e) => setForm({ ...form, montant: e.target.value })} placeholder="0" />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-label-md text-muted">FCFA</span>
              </div>
            </div>
            <button onClick={enregistrer} disabled={!canSubmit || busy} className="mt-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container shadow-sm disabled:opacity-50">
              <Icon name="save" className="text-[18px]" /> {busy ? 'Enregistrement…' : "Enregistrer l'avance"}
            </button>
          </Card>

          <div className="lg:col-span-2">
            <Card className="p-0 overflow-hidden">
              <div className="p-5 border-b border-border flex items-center justify-between gap-2">
                <div className="flex items-center gap-2"><Icon name="list_alt" className="text-muted" /><h3 className="text-subtitle-md font-bold text-ink">Avances du mois</h3></div>
                <Badge tone="neutral">{MOIS[open.mois]} {open.annee}</Badge>
              </div>
              {list == null ? (
                <div className="p-6 flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
              ) : list.length === 0 ? (
                <div className="p-10 text-center text-muted"><Icon name="payments" className="text-[40px] text-outline-variant" /><p className="mt-2">Aucune avance enregistrée ce mois.</p></div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-body-sm">
                    <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wide">
                      <th className="py-3 px-5">Salarié</th><th className="py-3 px-4 text-right">Montant de l'avance</th>
                    </tr></thead>
                    <tbody className="divide-y divide-border text-ink">
                      {list.map((v) => (
                        <tr key={v.id} className="hover:bg-primary-fixed/10">
                          <td className="py-3 px-5"><span className="font-bold">{v.nom}</span> <span className="text-muted font-mono text-label-md">{v.matricule}</span></td>
                          <td className="py-3 px-4 text-right tabular-nums font-semibold text-danger">- {fcfa(v.montant)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot><tr className="bg-primary/5 border-t-2 border-primary font-extrabold text-ink">
                      <td className="py-3 px-5">TOTAL ({list.length})</td>
                      <td className="py-3 px-4 text-right tabular-nums text-danger">- {fcfa(total)}</td>
                    </tr></tfoot>
                  </table>
                </div>
              )}
              <p className="p-4 text-label-md text-muted flex items-start gap-1.5"><Icon name="info" className="text-[16px] mt-0.5" />Les avances sont déduites du net à payer au prochain calcul de la paie. Recalculez le cycle pour les répercuter.</p>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}
