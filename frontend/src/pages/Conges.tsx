import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, type Employee, type LeaveRequest } from '../api'
import { Badge, Card, Icon } from '../stitch'

const TYPES: { key: string; label: string }[] = [
  { key: 'conge_annuel', label: 'Congé annuel' },
  { key: 'maladie', label: 'Maladie' },
  { key: 'maternite', label: 'Maternité' },
  { key: 'sans_solde', label: 'Sans solde' },
  { key: 'autre', label: 'Autre' },
]
const TLABEL = Object.fromEntries(TYPES.map((t) => [t.key, t.label]))
const STATUT: Record<string, { label: string; tone: 'warning' | 'success' | 'danger' }> = {
  en_attente: { label: 'En attente', tone: 'warning' },
  valide: { label: 'Validé', tone: 'success' },
  refuse: { label: 'Refusé', tone: 'danger' },
}

/** Jours calendaires inclusifs entre deux dates ISO (indicatif ; l'ajustement ouvrés reste manuel). */
function joursEntre(d1: string, d2: string): number {
  const a = new Date(d1), b = new Date(d2)
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime()) || b < a) return 0
  return Math.round((b.getTime() - a.getTime()) / 86400000) + 1
}

export default function Conges() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [emps, setEmps] = useState<Employee[]>([])
  const [list, setList] = useState<LeaveRequest[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ employee_id: '', type: 'conge_annuel', date_debut: '', date_fin: '', motif: '' })

  const reload = () => api.leaves(cid).then((r) => setList(r.leaves)).catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  useEffect(() => { api.employees(cid).then((r) => setEmps(r.employes)).catch(() => undefined); reload() }, [cid])

  const jours = joursEntre(form.date_debut, form.date_fin)
  const canSubmit = form.employee_id && form.date_debut && form.date_fin && jours > 0

  const soumettre = () => {
    if (!canSubmit) return
    setBusy(true); setError(null)
    api.createLeave({ company_id: cid, employee_id: form.employee_id, type: form.type, date_debut: form.date_debut, date_fin: form.date_fin, jours, motif: form.motif || null })
      .then(() => { setForm({ employee_id: '', type: 'conge_annuel', date_debut: '', date_fin: '', motif: '' }); return reload() })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
      .finally(() => setBusy(false))
  }
  const statuer = (id: string, accord: boolean) => {
    setBusy(true); setError(null)
    api.validateLeave(id, accord).then(reload).catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau')).finally(() => setBusy(false))
  }

  const champ = 'w-full px-3 py-2.5 rounded-xl border border-border bg-white text-ink outline-none focus:border-secondary-fixed-dim focus:ring-2 focus:ring-secondary-fixed-dim/30'

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Congés &amp; absences</h2>
          <Badge tone="secondary" icon="event">Code du Travail Bénin</Badge>
        </div>
        <p className="text-body-md text-muted mt-1 max-w-2xl">Demandes de congés et absences, avec validation à deux niveaux (demande → validation par un responsable).</p>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Nouvelle demande */}
        <Card className="p-5 lg:col-span-1 h-fit flex flex-col gap-3">
          <div className="flex items-center gap-2"><Icon name="add_circle" className="text-secondary" /><h3 className="text-subtitle-md font-bold text-ink">Nouvelle demande</h3></div>
          <div><span className="block text-label-md font-semibold text-ink mb-1">Salarié</span>
            <select className={champ} value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })}>
              <option value="">— Sélectionner —</option>
              {emps.map((e) => <option key={e.id} value={e.id}>{e.nom} ({e.matricule})</option>)}
            </select></div>
          <div><span className="block text-label-md font-semibold text-ink mb-1">Type</span>
            <select className={champ} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              {TYPES.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
            </select></div>
          <div className="grid grid-cols-2 gap-2">
            <div><span className="block text-label-md font-semibold text-ink mb-1">Du</span><input type="date" className={champ} value={form.date_debut} onChange={(e) => setForm({ ...form, date_debut: e.target.value })} /></div>
            <div><span className="block text-label-md font-semibold text-ink mb-1">Au</span><input type="date" className={champ} value={form.date_fin} onChange={(e) => setForm({ ...form, date_fin: e.target.value })} /></div>
          </div>
          <div className="text-label-md text-muted">Durée : <span className="font-bold text-ink">{jours} jour{jours > 1 ? 's' : ''}</span> (calendaires)</div>
          <div><span className="block text-label-md font-semibold text-ink mb-1">Motif (optionnel)</span><input className={champ} value={form.motif} onChange={(e) => setForm({ ...form, motif: e.target.value })} placeholder="Ex. congés annuels" /></div>
          <button onClick={soumettre} disabled={!canSubmit || busy}
            className="mt-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container shadow-sm disabled:opacity-50">
            <Icon name="send" className="text-[18px]" /> {busy ? 'Envoi…' : 'Soumettre la demande'}
          </button>
        </Card>

        {/* Liste */}
        <div className="lg:col-span-2">
          <Card className="p-0 overflow-hidden">
            <div className="p-5 border-b border-border flex items-center gap-2"><Icon name="list_alt" className="text-muted" /><h3 className="text-subtitle-md font-bold text-ink">Demandes</h3></div>
            {list == null ? (
              <div className="p-6 flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
            ) : list.length === 0 ? (
              <div className="p-10 text-center text-muted"><Icon name="event_available" className="text-[40px] text-outline-variant" /><p className="mt-2">Aucune demande de congé.</p></div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-body-sm">
                  <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wide">
                    <th className="py-3 px-4">Salarié</th><th className="py-3 px-3">Type</th><th className="py-3 px-3">Période</th>
                    <th className="py-3 px-3 text-right">Jours</th><th className="py-3 px-3">Statut</th><th className="py-3 px-4 text-right">Action</th>
                  </tr></thead>
                  <tbody className="divide-y divide-border text-ink">
                    {list.map((l) => (
                      <tr key={l.id} className="hover:bg-primary-fixed/10">
                        <td className="py-2.5 px-4"><span className="font-bold">{l.nom}</span> <span className="text-muted font-mono text-label-md">{l.matricule}</span></td>
                        <td className="py-2.5 px-3">{TLABEL[l.type] ?? l.type}</td>
                        <td className="py-2.5 px-3 text-muted tabular-nums">{l.date_debut} → {l.date_fin}</td>
                        <td className="py-2.5 px-3 text-right tabular-nums font-semibold">{l.jours}</td>
                        <td className="py-2.5 px-3"><Badge tone={STATUT[l.statut]?.tone ?? 'neutral'}>{STATUT[l.statut]?.label ?? l.statut}</Badge></td>
                        <td className="py-2.5 px-4 text-right">
                          {l.statut === 'en_attente' ? (
                            <div className="inline-flex items-center gap-1.5">
                              <button onClick={() => statuer(l.id, true)} disabled={busy} className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-success text-white font-bold text-label-md rounded-lg hover:opacity-90 disabled:opacity-50"><Icon name="check" className="text-[16px]" /> Valider</button>
                              <button onClick={() => statuer(l.id, false)} disabled={busy} className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-surface-container text-danger font-bold text-label-md rounded-lg hover:bg-danger/10 disabled:opacity-50"><Icon name="close" className="text-[16px]" /> Refuser</button>
                            </div>
                          ) : <span className="text-muted text-label-md">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="p-4 text-label-md text-muted flex items-start gap-1.5"><Icon name="info" className="text-[16px] mt-0.5" />La durée affichée est calendaire ; l'imputation sur le solde et la paie suit les règles légales du moteur.</p>
          </Card>
        </div>
      </div>
    </div>
  )
}
