import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError, type Company } from '../api'
import { Icon } from '../stitch'

const AVA = ['bg-primary/10 text-primary', 'bg-secondary/10 text-secondary', 'bg-primary-container text-secondary-fixed', 'bg-surface-container-highest text-primary']

export default function Companies() {
  const [companies, setCompanies] = useState<Company[] | null>(null)
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [headcount, setHeadcount] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const navigate = useNavigate()

  useEffect(() => {
    let alive = true
    api.companies().then(async (r) => {
      if (!alive) return
      setCompanies(r.companies)
      try {
        const per = await Promise.all(r.companies.map((c) => api.employees(c.id).then((e) => [c.id, e.employes.length] as const).catch(() => [c.id, 0] as const)))
        if (!alive) return
        const map: Record<string, number> = {}; let t = 0
        for (const [id, n] of per) { map[id] = n; t += n }
        setCounts(map); setHeadcount(t)
      } catch { /* indisponible */ }
    }).catch((e) => alive && setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
    return () => { alive = false }
  }, [])

  const filtered = useMemo(() => {
    if (!companies) return null
    const n = q.trim().toLowerCase()
    return n ? companies.filter((c) => [c.raison_sociale, c.nom, c.ifu].some((v) => v?.toLowerCase().includes(n))) : companies
  }, [companies, q])
  const nb = companies?.length ?? null

  return (
    <div className="space-y-6">
      {/* En-tête */}
      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-headline-lg font-headline-lg text-ink font-extrabold tracking-tight">Portefeuille des sociétés</h1>
            {nb != null && <span className="inline-flex items-center bg-secondary-fixed/30 text-secondary px-3 py-1 rounded-full text-label-md font-bold">{nb} dossier{nb > 1 ? 's' : ''} actif{nb > 1 ? 's' : ''}</span>}
          </div>
          <p className="text-body-md text-muted mt-1 max-w-2xl">Supervision globale des cycles de paie, conformité DGI (ITS/VPS) et CNSS Bénin pour l’ensemble de vos clients.</p>
        </div>
        <button onClick={() => navigate('/nouvelle-societe')} className="inline-flex items-center gap-2 px-4 py-2.5 bg-secondary-fixed text-ink font-extrabold rounded-xl hover:bg-secondary-fixed-dim shadow-sm shrink-0"><Icon name="add_business" className="text-[18px]" />Nouvelle société</button>
      </div>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {/* 3 KPI */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-surface rounded-2xl p-5 border border-border shadow-sm">
          <div className="flex items-start justify-between"><span className="text-label-md uppercase tracking-wider text-muted font-semibold">Sociétés au portefeuille</span>
            <span className="w-9 h-9 rounded-xl bg-surface-container text-primary flex items-center justify-center"><Icon name="domain" className="text-[20px]" /></span></div>
          <div className="text-[32px] font-extrabold text-primary tabular-nums mt-1 leading-none">{nb ?? '—'}</div>
          <div className="mt-3 pt-3 border-t border-border flex items-center justify-between text-label-md"><span className="text-success font-semibold">100% actives</span><span className="text-primary font-bold">{headcount ?? '…'} salariés gérés</span></div>
        </div>
        <div className="bg-surface rounded-2xl p-5 border border-border shadow-sm">
          <div className="flex items-start justify-between"><span className="text-label-md uppercase tracking-wider text-muted font-semibold">Effectif total géré</span>
            <span className="w-9 h-9 rounded-xl bg-secondary-fixed/30 text-secondary flex items-center justify-center"><Icon name="groups" className="text-[20px]" /></span></div>
          <div className="text-[32px] font-extrabold text-primary tabular-nums mt-1 leading-none">{headcount ?? '—'}</div>
          <div className="mt-3 pt-3 border-t border-border text-label-md text-muted">Salariés actifs sur le périmètre</div>
        </div>
        <div className="bg-surface rounded-2xl p-5 border border-border shadow-sm">
          <div className="flex items-start justify-between"><span className="text-label-md uppercase tracking-wider text-muted font-semibold">Conformité</span>
            <span className="w-9 h-9 rounded-xl bg-success/10 text-success flex items-center justify-center"><Icon name="verified_user" className="text-[20px]" /></span></div>
          <div className="text-[22px] font-extrabold text-success mt-2 leading-none">Barèmes à jour</div>
          <div className="mt-3 pt-3 border-t border-border text-label-md text-muted">DGI ITS/VPS &amp; CNSS intégrés</div>
        </div>
      </section>

      {/* Filtre */}
      <div className="bg-surface rounded-2xl p-3 border border-border shadow-sm flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-muted text-[18px]" />
          <input value={q} onChange={(e) => setParams(e.target.value ? { q: e.target.value } : {}, { replace: true })} placeholder="Filtrer par société ou IFU…" className="w-full pl-9 pr-3 py-2 text-body-md bg-background border border-border rounded-xl focus:border-secondary focus:ring-1 focus:ring-secondary outline-none" />
        </div>
      </div>

      {/* Table */}
      <section className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden">
        {filtered == null ? <div className="p-6 flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
          : filtered.length === 0 ? (
            <div className="p-10 text-center text-muted">{q ? 'Aucune société ne correspond.' : <>Aucune société. <Link to="/nouvelle-societe" className="text-secondary font-bold hover:underline">Créer une société</Link>.</>}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wider">
                  <th className="py-3 px-6">Société &amp; IFU officiel</th><th className="py-3 px-4">Salariés</th><th className="py-3 px-4">Statut du cycle</th><th className="py-3 px-6 text-center">Actions</th>
                </tr></thead>
                <tbody className="divide-y divide-border text-body-md text-ink">
                  {filtered.map((c, i) => {
                    const nom = c.raison_sociale ?? c.nom ?? 'Société'
                    return (
                      <tr key={c.id} className="hover:bg-primary-fixed/20 transition-colors">
                        <td className="py-4 px-6"><div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm ${AVA[i % AVA.length]}`}>{nom.slice(0, 2).toUpperCase()}</div>
                          <div className="flex flex-col"><span className="font-bold text-ink">{nom}</span>
                            <span className="text-label-md text-muted font-mono">{c.ifu ? `IFU : ${c.ifu}` : 'IFU non renseigné'}</span></div></div></td>
                        <td className="py-4 px-4 font-semibold tabular-nums">{counts[c.id] ?? '—'}</td>
                        <td className="py-4 px-4"><span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-label-md font-bold bg-surface-container text-primary"><Icon name="sync" className="text-[14px]" />À préparer</span></td>
                        <td className="py-4 px-6 text-center"><div className="flex items-center justify-center gap-2">
                          <Link to={`/c/${c.id}`} className="px-2.5 py-1 bg-surface-container text-ink hover:bg-border rounded-lg text-label-md font-semibold transition-colors">Ouvrir</Link>
                          <Link to={`/c/${c.id}/paie`} className="text-secondary hover:underline text-label-md font-bold flex items-center gap-0.5">Paie <Icon name="chevron_right" className="text-[14px]" /></Link></div></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
      </section>
    </div>
  )
}
