import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError, type Company } from '../api'
import { Icon } from '../stitch'

const MOIS = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
const AVA = ['bg-primary/10 text-primary', 'bg-secondary/10 text-secondary', 'bg-primary-container text-secondary-fixed', 'bg-surface-container-highest text-primary']

// Étape de cycle (indicateur visuel du héros, markup Stitch exact).
function Step({ n, label, state }: { n: number; label: string; state: 'done' | 'active' | 'todo' }) {
  if (state === 'done') return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="w-7 h-7 rounded-full bg-secondary-fixed text-primary flex items-center justify-center font-bold text-xs"><Icon name="check" className="text-[16px]" /></div>
      <span className="text-[11px] font-semibold text-secondary-fixed">{n}. {label}</span>
    </div>
  )
  if (state === 'active') return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="w-7 h-7 rounded-full bg-surface-container-lowest text-primary ring-4 ring-secondary-fixed/30 flex items-center justify-center font-extrabold text-xs">{n}</div>
      <span className="text-[11px] font-bold text-surface-container-lowest">{n}. {label}</span>
    </div>
  )
  return (
    <div className="flex flex-col items-center gap-1.5 opacity-50">
      <div className="w-7 h-7 rounded-full bg-on-primary-container/30 text-surface-container-lowest flex items-center justify-center font-bold text-xs">{n}</div>
      <span className="text-[11px] font-medium text-on-primary-container">{n}. {label}</span>
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [companies, setCompanies] = useState<Company[] | null>(null)
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [headcount, setHeadcount] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api.companies().then(async (r) => {
      if (!alive) return
      setCompanies(r.companies)
      try {
        const per = await Promise.all(r.companies.map((c) => api.employees(c.id).then((e) => [c.id, e.employes.length] as const).catch(() => [c.id, 0] as const)))
        if (!alive) return
        const map: Record<string, number> = {}; let total = 0
        for (const [id, n] of per) { map[id] = n; total += n }
        setCounts(map); setHeadcount(total)
      } catch { /* effectif indisponible */ }
    }).catch((e) => alive && setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
    return () => { alive = false }
  }, [])

  const now = new Date()
  const periode = `${MOIS[now.getMonth() + 1]} ${now.getFullYear()}`
  const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1)
  const echFisc = new Date(nextMonth.getFullYear(), nextMonth.getMonth(), 10)
  const echCnss = new Date(nextMonth.getFullYear(), nextMonth.getMonth(), 15)
  const jDiff = (d: Date) => Math.round((d.getTime() - now.getTime()) / 86400000)
  const fmtDate = (d: Date) => `${d.getDate()} ${MOIS[d.getMonth() + 1]} ${d.getFullYear()}`
  const nbSoc = companies?.length ?? null

  return (
    <div className="flex flex-col gap-6">
      {/* En-tête */}
      <section className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-headline-lg font-headline-lg text-ink tracking-tight">Tableau de bord</h1>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-label-md font-label-md bg-secondary/10 text-secondary border border-secondary/20">
              <span className="w-2 h-2 rounded-full bg-secondary"></span>Période active
            </span>
          </div>
          <p className="text-body-md font-body-md text-muted mt-1">Supervision des cycles de paie, conformité fiscale DGI et déclarations sociales CNSS Bénin.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-surface px-3 py-1.5 rounded-xl border border-border shadow-sm">
            <Icon name="calendar_today" className="text-muted text-[18px]" />
            <span className="text-label-lg font-bold text-ink">{periode}</span>
          </div>
          <button onClick={() => navigate('/portefeuille')} className="flex items-center gap-1.5 px-3 py-1.5 bg-surface text-ink hover:bg-surface-container border border-border rounded-xl text-label-lg font-semibold transition-colors shadow-sm">
            <Icon name="tune" className="text-[18px]" /><span>Filtres</span>
          </button>
        </div>
      </section>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {/* 3 KPI */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-surface p-space-lg rounded-2xl border border-border shadow-sm flex flex-col justify-between hover:border-outline-variant transition-colors">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="text-label-lg font-label-lg text-muted">Sociétés gérées</span>
              <span className="text-[32px] font-headline-lg text-primary tabular-nums mt-1 leading-none">{nbSoc ?? '—'}</span>
            </div>
            <div className="w-10 h-10 rounded-xl bg-surface-container flex items-center justify-center text-primary"><Icon name="domain" className="text-[22px]" /></div>
          </div>
          <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-label-md">
            <span className="text-muted">Dans votre périmètre</span>
            <Link to="/portefeuille" className="text-secondary font-bold flex items-center gap-0.5 hover:underline">Voir <Icon name="arrow_forward" className="text-[14px]" /></Link>
          </div>
        </div>
        <div className="bg-surface p-space-lg rounded-2xl border border-border shadow-sm flex flex-col justify-between hover:border-outline-variant transition-colors">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="text-label-lg font-label-lg text-muted">Salariés actifs</span>
              <span className="text-[32px] font-headline-lg text-primary tabular-nums mt-1 leading-none">{headcount ?? '—'}</span>
            </div>
            <div className="w-10 h-10 rounded-xl bg-surface-container flex items-center justify-center text-primary"><Icon name="badge" className="text-[22px]" /></div>
          </div>
          <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-label-md">
            <span className="text-muted">{headcount == null ? 'Calcul en cours…' : 'Sur l’ensemble du portefeuille'}</span>
          </div>
        </div>
        <div className="bg-surface p-space-lg rounded-2xl border border-border shadow-sm flex flex-col justify-between hover:border-outline-variant transition-colors">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="text-label-lg font-label-lg text-muted">Masse salariale globale</span>
              <div className="text-[26px] font-headline-lg text-primary tabular-nums mt-1 leading-none">— <span className="text-subtitle-md font-semibold text-secondary">FCFA</span></div>
            </div>
            <div className="w-10 h-10 rounded-xl bg-surface-container flex items-center justify-center text-primary"><Icon name="payments" className="text-[22px]" /></div>
          </div>
          <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-label-md">
            <span className="text-muted">Disponible après un cycle calculé</span>
          </div>
        </div>
      </section>

      {/* Héros + échéances */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-8 bg-primary-container text-surface-container-lowest rounded-2xl p-6 border border-border/10 shadow-sm flex flex-col justify-between relative overflow-hidden">
          <div className="flex flex-col gap-4 relative z-10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-lg bg-surface-container-lowest/10 text-secondary-fixed text-label-md font-bold tracking-wide uppercase">Action prioritaire</span>
                <span className="text-label-md text-on-primary-container">{periode}</span>
              </div>
              <span className="inline-flex items-center gap-1 text-label-md text-secondary-fixed bg-secondary-fixed/10 px-2.5 py-1 rounded-full font-bold"><Icon name="hourglass_top" className="text-[16px]" />Étape 1 / 6</span>
            </div>
            <div>
              <h2 className="text-headline-md font-headline-md text-surface-container-lowest">Cycle de paie — {periode}</h2>
              <p className="text-body-md font-body-md text-on-primary-container mt-1 max-w-2xl">
                {nbSoc === 0 ? "Aucune société enregistrée. Créez votre première société pour lancer un cycle."
                  : `${nbSoc ?? '…'} société${(nbSoc ?? 0) > 1 ? 's' : ''} dans votre périmètre. Ouvrez une société pour saisir les variables et calculer les bulletins.`}
              </p>
            </div>
            <div className="mt-2 bg-primary/40 rounded-xl p-4 border border-on-primary-container/20">
              <div className="grid grid-cols-6 gap-2 text-center">
                <Step n={1} label="Préparer" state="active" />
                <Step n={2} label="Variables" state="todo" />
                <Step n={3} label="Vérifier" state="todo" />
                <Step n={4} label="Calculer" state="todo" />
                <Step n={5} label="Valider" state="todo" />
                <Step n={6} label="Finaliser" state="todo" />
              </div>
              <div className="w-full bg-primary/60 h-1.5 rounded-full mt-3 overflow-hidden"><div className="bg-secondary-fixed h-full rounded-full" style={{ width: '16%' }}></div></div>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-on-primary-container/20">
            <div className="flex items-center gap-4 text-label-md text-on-primary-container">
              <span className="flex items-center gap-1.5"><Icon name="done_all" className="text-secondary-fixed text-[16px]" />Barème ITS/VPS &amp; taux CNSS intégrés</span>
            </div>
            <Link to={nbSoc === 0 ? '/nouvelle-societe' : '/portefeuille'} className="px-6 py-3 bg-secondary-fixed hover:bg-secondary-fixed-dim text-ink font-extrabold text-subtitle-md rounded-xl transition-all duration-150 active:scale-95 shadow-md flex items-center gap-2">
              <span>{nbSoc === 0 ? 'Créer une société' : 'Aller à la paie'}</span><Icon name="arrow_forward" className="text-[18px]" />
            </Link>
          </div>
        </div>

        <div className="lg:col-span-4 bg-surface rounded-2xl p-6 border border-border shadow-sm flex flex-col justify-between">
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-subtitle-lg font-subtitle-lg text-ink">Échéances déclaratives</h3>
              <span className="text-[11px] font-bold text-secondary uppercase bg-secondary/10 px-2 py-0.5 rounded">Bénin Fiscal</span>
            </div>
            <p className="text-body-md text-muted">Calendrier réglementaire pour les déclarations fiscales et sociales.</p>
            <div className="flex flex-col gap-3 mt-1">
              <div className="p-3 rounded-xl bg-surface-container-low border border-border flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-warning/10 text-warning flex items-center justify-center shrink-0 mt-0.5"><Icon name="gavel" className="text-[18px]" /></div>
                  <div className="flex flex-col">
                    <div className="text-label-lg font-bold text-ink">Déclaration ITS / VPS</div>
                    <span className="text-label-md text-muted">Impôt Traitements &amp; Salaires — DGI Bénin</span>
                    <span className="text-[11px] text-danger font-semibold mt-0.5">Date limite : {fmtDate(echFisc)}</span>
                  </div>
                </div>
                <span className="px-2 py-1 rounded bg-warning/15 text-warning font-bold text-label-md shrink-0">J-{jDiff(echFisc)}</span>
              </div>
              <div className="p-3 rounded-xl bg-surface-container-low border border-border flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5"><Icon name="verified" className="text-[18px]" /></div>
                  <div className="flex flex-col">
                    <div className="text-label-lg font-bold text-ink">Déclaration CNSS</div>
                    <span className="text-label-md text-muted">Cotisations sociales Cotonou</span>
                    <span className="text-[11px] text-muted font-medium mt-0.5">Date limite : {fmtDate(echCnss)}</span>
                  </div>
                </div>
                <span className="px-2 py-1 rounded bg-surface-container text-ink font-bold text-label-md shrink-0">J-{jDiff(echCnss)}</span>
              </div>
            </div>
          </div>
          <Link to="/conformite" className="mt-4 pt-4 border-t border-border flex items-center gap-2 text-label-md text-secondary hover:underline">
            <Icon name="verified_user" className="text-[18px]" /><span className="font-semibold">Barème fiscal DGI &amp; taux CNSS à jour</span>
          </Link>
        </div>
      </section>

      {/* Portefeuille */}
      <section className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden flex flex-col">
        <div className="p-4 px-6 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-surface">
          <div className="flex items-center gap-3">
            <h3 className="text-subtitle-lg font-subtitle-lg text-ink">Portefeuille des clients &amp; sociétés</h3>
            {nbSoc != null && <span className="px-2 py-0.5 text-label-md font-bold bg-surface-container text-muted rounded-full">{nbSoc} {nbSoc > 1 ? 'dossiers' : 'dossier'}</span>}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => navigate('/nouvelle-societe')} className="px-3 py-1.5 text-label-md font-bold text-ink bg-surface border border-border rounded-xl hover:bg-surface-container transition-colors flex items-center gap-1.5 shadow-sm"><Icon name="add_business" className="text-[16px]" /><span>Nouvelle société</span></button>
          </div>
        </div>
        {companies == null ? (
          <div className="p-6 flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
        ) : companies.length === 0 ? (
          <div className="p-8 text-center text-muted">Aucune société dans votre périmètre. <Link to="/nouvelle-societe" className="text-secondary font-bold hover:underline">Créer une société</Link>.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-border text-label-lg font-bold text-muted">
                  <th className="py-3 px-6">Société</th>
                  <th className="py-3 px-4">Salariés</th>
                  <th className="py-3 px-4">Statut du cycle</th>
                  <th className="py-3 px-4">Échéance DGI/CNSS</th>
                  <th className="py-3 px-6 text-center">Actions rapides</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-body-md font-body-md text-ink">
                {companies.map((c, i) => {
                  const nom = c.raison_sociale ?? c.nom ?? 'Société'
                  return (
                    <tr key={c.id} className="hover:bg-primary-fixed/20 transition-colors">
                      <td className="py-3.5 px-6">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs ${AVA[i % AVA.length]}`}>{nom.slice(0, 2).toUpperCase()}</div>
                          <div className="flex flex-col">
                            <span className="font-bold text-ink">{nom}</span>
                            <span className="text-label-md text-muted">{c.ifu ? `IFU : ${c.ifu}` : 'IFU non renseigné'}</span>
                          </div>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-semibold tabular-nums">{counts[c.id] ?? '—'}</td>
                      <td className="py-3.5 px-4">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-label-md font-bold bg-surface-container text-primary"><Icon name="sync" className="text-[14px]" />À préparer</span>
                      </td>
                      <td className="py-3.5 px-4 text-label-md">
                        <div className="flex flex-col"><span className="font-semibold text-ink">{fmtDate(echFisc)}</span><span className="text-muted">ITS/VPS · CNSS</span></div>
                      </td>
                      <td className="py-3.5 px-6 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <Link to={`/c/${c.id}`} className="px-2.5 py-1 bg-surface-container text-ink hover:bg-border rounded-lg text-label-md font-semibold transition-colors">Ouvrir</Link>
                          <Link to={`/c/${c.id}/paie`} className="text-secondary hover:underline text-label-md font-bold flex items-center gap-0.5">Paie <Icon name="chevron_right" className="text-[14px]" /></Link>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="p-4 px-6 border-t border-border flex items-center justify-between text-label-md text-muted bg-surface-bright">
          <span className="text-secondary font-semibold">Barèmes conformes au Code Général des Impôts (CGI Bénin)</span>
        </div>
      </section>
    </div>
  )
}
