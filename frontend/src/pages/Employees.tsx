import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Employee } from '../api'
import { Icon } from '../stitch'

const PAIEMENT: Record<string, { label: string; cls: string; icon: string }> = {
  especes: { label: 'Espèces', cls: 'bg-surface-container text-ink', icon: 'payments' },
  virement: { label: 'Virement', cls: 'bg-primary/5 text-primary', icon: 'account_balance' },
  mobile_money: { label: 'Mobile Money', cls: 'bg-warning/10 text-warning', icon: 'smartphone' },
  momo: { label: 'Mobile Money', cls: 'bg-warning/10 text-warning', icon: 'smartphone' },
}

export default function Employees() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [list, setList] = useState<Employee[] | null>(null)
  const [sel, setSel] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ matricule: '', nom: '', salaire_base: '', num_cnss: '' })
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  function load() {
    setError(null)
    api.employees(cid).then((r) => { setList(r.employes); if (r.employes[0] && !sel) setSel(r.employes[0].id) })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }
  useEffect(load, [cid]) // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => {
    if (!list) return null
    const n = q.trim().toLowerCase()
    return n ? list.filter((e) => [e.nom, e.matricule].some((v) => v?.toLowerCase().includes(n))) : list
  }, [list, q])
  const current = list?.find((e) => e.id === sel) ?? null

  async function submit(e: FormEvent) {
    e.preventDefault(); setFormError(null); setBusy(true)
    try {
      const r = await api.createEmployee({ company_id: cid, matricule: form.matricule.trim(), nom: form.nom.trim(), salaire_base: Number(form.salaire_base), num_cnss: form.num_cnss.trim() || null })
      setForm({ matricule: '', nom: '', salaire_base: '', num_cnss: '' }); setOpen(false); setSel(r.employee_id); load()
    } catch (err) { setFormError(err instanceof ApiError ? err.message : 'Erreur réseau') } finally { setBusy(false) }
  }

  return (
    <div className="flex flex-col gap-5">
      {/* En-tête */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-headline-lg font-headline-lg text-ink font-extrabold tracking-tight">Équipe &amp; Salariés</h1>
          {list && <span className="inline-flex items-center gap-1.5 bg-secondary-fixed/30 text-secondary px-3 py-1 rounded-full text-label-md font-bold">{list.length} salarié{list.length > 1 ? 's' : ''} actif{list.length > 1 ? 's' : ''}</span>}
        </div>
        <div className="flex items-center gap-2">
          <button className="inline-flex items-center gap-2 px-3.5 py-2 border border-border rounded-xl text-label-md font-semibold text-ink bg-surface hover:bg-surface-container transition-colors shadow-xs"><Icon name="download" className="text-base" /><span>Export DGI &amp; CNSS</span></button>
          <button onClick={() => setOpen((v) => !v)} className="inline-flex items-center gap-2 px-4 py-2 bg-secondary-fixed text-ink font-extrabold rounded-xl hover:bg-secondary-fixed-dim shadow-sm"><Icon name="person_add" className="text-base" /><span>{open ? 'Fermer' : 'Ajouter un salarié'}</span></button>
        </div>
      </div>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {open && (
        <div className="bg-surface rounded-2xl border border-border shadow-sm p-5">
          <form onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="space-y-1.5"><span className="block text-label-lg font-semibold text-ink">Matricule</span><input value={form.matricule} onChange={(e) => setForm({ ...form, matricule: e.target.value })} required className="w-full px-3 py-2.5 bg-white rounded-xl border border-border outline-none focus:border-secondary" /></label>
            <label className="space-y-1.5"><span className="block text-label-lg font-semibold text-ink">Nom complet</span><input value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} required className="w-full px-3 py-2.5 bg-white rounded-xl border border-border outline-none focus:border-secondary" /></label>
            <label className="space-y-1.5"><span className="block text-label-lg font-semibold text-ink">Salaire de base (FCFA)</span><input type="number" value={form.salaire_base} onChange={(e) => setForm({ ...form, salaire_base: e.target.value })} required className="w-full px-3 py-2.5 bg-white rounded-xl border border-border outline-none focus:border-secondary" /></label>
            <label className="space-y-1.5"><span className="block text-label-lg font-semibold text-ink">N° CNSS (optionnel)</span><input value={form.num_cnss} onChange={(e) => setForm({ ...form, num_cnss: e.target.value })} className="w-full px-3 py-2.5 bg-white rounded-xl border border-border outline-none focus:border-secondary" /></label>
            {formError && <div className="sm:col-span-2 p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{formError}</div>}
            <div className="sm:col-span-2"><button type="submit" disabled={busy} className="inline-flex items-center gap-2 px-4 py-2.5 bg-secondary-fixed text-ink font-extrabold rounded-xl hover:bg-secondary-fixed-dim disabled:opacity-50"><Icon name="check" className="text-[18px]" />{busy ? 'Enregistrement…' : 'Créer le salarié'}</button></div>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_42%] gap-5">
        {/* Liste */}
        <section className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden flex flex-col">
          <div className="p-3 border-b border-border">
            <div className="relative">
              <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-muted text-[18px]" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtrer par nom, matricule…" className="w-full pl-9 pr-3 py-2 text-body-md bg-background border border-border rounded-xl focus:border-secondary focus:ring-1 focus:ring-secondary outline-none" />
            </div>
          </div>
          {filtered == null ? <div className="p-6 flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
            : filtered.length === 0 ? <div className="p-8 text-center text-muted">Aucun salarié.</div> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted">
                    <th className="py-2.5 px-4">Salarié</th><th className="py-2.5 px-3">Matricule</th><th className="py-2.5 px-3">Paiement</th><th className="py-2.5 px-3 text-right">Salaire</th>
                  </tr></thead>
                  <tbody className="divide-y divide-border text-body-md text-ink">
                    {filtered.map((e) => {
                      const pay = PAIEMENT[e.methode_paiement ?? ''] ?? { label: e.methode_paiement ?? '—', cls: 'bg-surface-container text-muted', icon: 'payments' }
                      const active = e.id === sel
                      return (
                        <tr key={e.id} onClick={() => setSel(e.id)} className={`cursor-pointer transition-colors ${active ? 'bg-secondary-fixed/10 border-l-2 border-secondary' : 'hover:bg-primary-fixed/20'}`}>
                          <td className="py-3 px-4"><div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">{e.nom.slice(0, 2).toUpperCase()}</div>
                            <span className="font-bold text-ink">{e.nom}</span></div></td>
                          <td className="py-3 px-3 text-label-md text-muted font-mono">{e.matricule}</td>
                          <td className="py-3 px-3"><span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-label-md font-semibold ${pay.cls}`}><Icon name={pay.icon} className="text-[13px]" />{pay.label}</span></td>
                          <td className="py-3 px-3 text-right font-bold tabular-nums">{fcfa(e.salaire_base ?? undefined)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
        </section>

        {/* Fiche */}
        <section className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden flex flex-col">
          {current ? (
            <>
              <div className="p-5 border-b border-border">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-2xl bg-primary-container text-surface-container-lowest flex items-center justify-center text-headline-md font-black shadow-md border-2 border-surface">{current.nom.slice(0, 2).toUpperCase()}</div>
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2"><h2 className="text-subtitle-lg font-subtitle-lg font-bold text-ink">{current.nom}</h2>
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-success/10 text-success border border-success/20"><span className="w-1.5 h-1.5 rounded-full bg-success"></span>Actif</span></div>
                      <span className="text-body-md text-muted font-mono">{current.matricule}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                <div className="rounded-xl border border-border bg-white p-4 shadow-sm">
                  <div className="flex items-center justify-between pb-3 border-b border-border mb-3">
                    <div className="flex items-center gap-2 text-primary text-subtitle-md font-bold"><Icon name="payments" className="text-secondary" /><span>Rémunération &amp; Salaire</span></div>
                    <span className="text-label-md bg-secondary-fixed/30 text-secondary font-bold px-2 py-0.5 rounded">Barème ITS</span>
                  </div>
                  <div className="p-3 rounded-lg bg-[#F8FAFC] border border-border mb-3">
                    <span className="text-label-md text-muted block mb-1">Salaire brut de base</span>
                    <span className="text-subtitle-lg font-extrabold text-primary tabular-nums">{fcfa(current.salaire_base ?? undefined)}</span>
                  </div>
                  <div className="space-y-2 text-body-md">
                    <div className="flex items-center justify-between py-1 text-sm border-b border-dashed border-border"><span className="text-muted">Mode de versement :</span>
                      <span className="font-semibold text-ink">{(PAIEMENT[current.methode_paiement ?? ''] ?? { label: current.methode_paiement ?? '—' }).label}</span></div>
                    <div className="flex items-center justify-between py-1 text-sm"><span className="text-muted">Net à payer :</span><span className="font-semibold text-ink">Calculé au cycle</span></div>
                  </div>
                </div>
                <div className="rounded-xl border border-border bg-white p-4 shadow-sm">
                  <div className="flex items-center justify-between pb-3 border-b border-border mb-3">
                    <div className="flex items-center gap-2 text-primary text-subtitle-md font-bold"><Icon name="description" className="text-secondary" /><span>Contrat de travail</span></div>
                  </div>
                  <p className="text-body-md text-muted">Type de contrat, dates, poste et n° CNSS : à compléter (module d’onboarding).</p>
                </div>
                <div className="flex items-center gap-2 pt-2">
                  <Link to={`/c/${cid}/paie`} className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container shadow-sm"><Icon name="receipt_long" className="text-[18px]" />Aller au cycle de paie</Link>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-muted">
              <Icon name="person_search" className="text-[40px] text-outline-variant" />
              <p className="mt-2">Sélectionnez un salarié pour voir sa fiche.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
