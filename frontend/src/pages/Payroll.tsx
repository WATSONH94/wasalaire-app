import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Company, type Controls, type Employee, type Payslip, type PayoutItem, type RubriqueCat } from '../api'
import { Icon } from '../stitch'
import BulletinModal from '../components/BulletinModal'

const MOIS = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

function StepCard({ n, titre, sous, state }: { n: number; titre: string; sous: string; state: 'done' | 'active' | 'todo' }) {
  if (state === 'active') return (
    <div className="flex flex-col gap-2 p-3 rounded-lg bg-secondary-fixed/15 border-2 border-secondary shadow-xs">
      <div className="flex items-center justify-between">
        <span className="text-xs text-secondary font-bold flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>ÉTAPE ACTUELLE</span>
        <span className="w-5 h-5 rounded-full bg-secondary text-on-secondary flex items-center justify-center text-xs font-bold">{n}</span>
      </div>
      <div><div className="text-sm text-primary font-bold">{titre}</div><div className="text-[11px] text-ink font-medium">{sous}</div></div>
      <div className="w-full bg-secondary-container h-1.5 rounded-full overflow-hidden"><div className="bg-secondary h-full w-2/3 rounded-full"></div></div>
    </div>
  )
  if (state === 'done') return (
    <div className="flex flex-col gap-2 p-3 rounded-lg bg-surface-container-low/40 border border-border">
      <div className="flex items-center justify-between"><span className="text-xs text-muted font-bold">ÉTAPE {n}</span>
        <span className="w-5 h-5 rounded-full bg-secondary text-on-secondary flex items-center justify-center"><Icon name="check" className="text-xs font-bold" /></span></div>
      <div><div className="text-sm text-ink font-bold">{titre}</div><div className="text-[11px] text-muted">{sous}</div></div>
      <div className="w-full bg-secondary h-1.5 rounded-full"></div>
    </div>
  )
  return (
    <div className="flex flex-col gap-2 p-3 rounded-lg bg-surface-container-low/30 border border-border opacity-70">
      <div className="flex items-center justify-between"><span className="text-xs text-muted font-semibold">ÉTAPE {n}</span>
        <span className="w-5 h-5 rounded-full bg-surface-variant text-muted flex items-center justify-center text-xs font-bold">{n}</span></div>
      <div><div className="text-sm text-muted font-bold">{titre}</div><div className="text-[11px] text-muted">{sous}</div></div>
      <div className="w-full bg-border h-1.5 rounded-full"></div>
    </div>
  )
}

function Kpi({ label, value, unit, icon, foot, footTone }: { label: string; value: string; unit?: string; icon: string; foot: string; footTone: string }) {
  return (
    <div className="bg-surface rounded-xl p-5 border border-border shadow-xs hover:border-secondary transition-all">
      <div className="flex items-center justify-between text-muted mb-2">
        <span className="text-label-md uppercase tracking-wider font-semibold">{label}</span>
        <span className="w-8 h-8 rounded-lg bg-surface-container-low text-primary flex items-center justify-center"><Icon name={icon} className="text-lg" /></span>
      </div>
      <div className="text-headline-md text-primary font-extrabold tabular-nums tracking-tight">{value} {unit && <span className="text-xs font-semibold text-muted">{unit}</span>}</div>
      <div className={`mt-2 flex items-center gap-1.5 text-xs font-bold ${footTone}`}><span>{foot}</span></div>
    </div>
  )
}

function Controle({ titre, desc, tag }: { titre: string; desc: string; tag: string }) {
  return (
    <div className="p-3.5 rounded-lg bg-surface-container-low/50 border border-border flex items-start gap-3">
      <Icon name="check_circle" className="text-success text-lg mt-0.5" />
      <div>
        <div className="text-label-lg text-ink font-bold">{titre}</div>
        <div className="text-xs text-muted mt-0.5">{desc}</div>
        <span className="inline-block mt-2 text-[10px] uppercase font-bold text-success bg-success/10 px-1.5 py-0.5 rounded">{tag}</span>
      </div>
    </div>
  )
}

export default function Payroll() {
  const { companyId } = useParams()
  const cid = companyId as string
  const now = new Date()
  const [mois, setMois] = useState(now.getMonth() + 1)
  const [annee, setAnnee] = useState(now.getFullYear())
  const [periodId, setPeriodId] = useState<string | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [controls, setControls] = useState<Controls | null>(null)
  const [payslips, setPayslips] = useState<Payslip[] | null>(null)
  const [employees, setEmployees] = useState<Employee[]>([])
  const [company, setCompany] = useState<Company | null>(null)
  const [rubs, setRubs] = useState<RubriqueCat[]>([])
  const [vr, setVr] = useState({ employee_id: '', code: 'prime', montant: '', hours: '', majoration: '0.12' })
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [closed, setClosed] = useState(false)
  const [bulletin, setBulletin] = useState<Payslip | null>(null)
  const [showVars, setShowVars] = useState(false)
  const [payout, setPayout] = useState<PayoutItem[] | null>(null)

  useEffect(() => { api.employees(cid).then((r) => setEmployees(r.employes)).catch(() => undefined) }, [cid])
  useEffect(() => { api.companies().then((r) => setCompany(r.companies.find((c) => c.id === cid) ?? null)).catch(() => undefined) }, [cid])
  useEffect(() => { api.rubriques().then((r) => setRubs(r.rubriques)).catch(() => undefined) }, [])

  // Reprise d'état : en revenant sur la page (ou en changeant de mois), on recharge
  // le cycle ACTIF déjà calculé pour cette période. Le non-expert ne « perd » pas sa
  // paie entre deux visites — ses bulletins et contrôles réapparaissent tels quels.
  useEffect(() => {
    let cancel = false
    setPeriodId(null); setRunId(null); setControls(null); setPayslips(null); setClosed(false); setPayout(null)
    api.companyRuns(cid).then(async (r) => {
      const match = r.runs.find((x) => x.mois === mois && x.annee === annee && x.actif !== false)
      if (!match || cancel) return
      const estClos = match.statut === 'cloturee'
      setPeriodId(match.period_id ?? null)
      setRunId(match.run_id)
      setClosed(estClos)
      const [ctrl, ps] = await Promise.all([api.controls(match.run_id), api.payslips(match.run_id)])
      if (cancel) return
      setControls(ctrl); setPayslips(ps.bulletins)
      // Cycle clôturé : recharger un éventuel décaissement déjà lancé (reprise d'état).
      if (estClos) {
        try { const po = await api.payoutList(match.run_id); if (!cancel) setPayout(po.items.length ? po.items : null) } catch { /* pas encore de lot */ }
      }
    }).catch(() => undefined)
    return () => { cancel = true }
  }, [cid, mois, annee])

  async function run(label: string, fn: () => Promise<void>) {
    setError(null); setBusy(label)
    try { await fn() } catch (e) { setError(e instanceof ApiError ? e.message : 'Erreur réseau') } finally { setBusy(null) }
  }
  const openPeriod = () => run('open', async () => {
    const r = await api.openPeriod({ company_id: cid, mois, annee })
    setPeriodId(r.period_id); setRunId(null); setControls(null); setPayslips(null); setClosed(false)
  })
  const addVariable = () => run('var', async () => {
    if (!periodId || !vr.employee_id) return
    let montant = Number(vr.montant)
    if (vr.code === 'heures_sup') {
      const emp = employees.find((e) => e.id === vr.employee_id)
      const base = emp?.salaire_base ?? 0
      const tauxHoraire = base / 173.33
      montant = Math.round(Number(vr.hours) * tauxHoraire * (1 + Number(vr.majoration)))
    }
    if (!montant) return
    await api.addVariable({ company_id: cid, period_id: periodId, employee_id: vr.employee_id, type: vr.code, montant })
    setVr({ ...vr, montant: '', hours: '' })
  })
  const calculate = () => run('calc', async () => {
    if (!periodId) return
    const periode = `${annee}-${String(mois).padStart(2, '0')}-01`
    const r = await api.calculate({ company_id: cid, period_id: periodId, periode })
    setRunId(r.run_id); setControls(await api.controls(r.run_id)); setPayslips((await api.payslips(r.run_id)).bulletins)
  })
  const close = () => run('close', async () => {
    if (!runId || !periodId) return
    await api.closeRun(runId, periodId); setClosed(true); setPayslips((await api.payslips(runId)).bulletins)
  })
  const decaisser = () => run('payout', async () => {
    if (!runId) return
    await api.createPayout(runId, cid)
    setPayout((await api.payoutList(runId)).items)
  })

  const kpis = useMemo(() => {
    if (!payslips) return null
    let brut = 0, net = 0, its = 0, cout = 0
    // net = net À PAYER (p.net = net_a_payer, avance déduite) : c'est le montant réellement
    // décaissé. Utiliser le net fiscal fausserait le « Net à payer global » avec une avance.
    for (const p of payslips) { brut += p.detail?.brut ?? p.brut; net += p.net; its += (p.detail?.its ?? 0) + (p.detail?.vps ?? 0); cout += p.detail?.cout_employeur ?? p.cout_employeur }
    return { brut, net, its, cout, n: payslips.length }
  }, [payslips])

  const societe = company?.raison_sociale ?? company?.nom ?? 'Société'
  const periode = `${MOIS[mois]} ${annee}`
  const step = closed ? 4 : payslips ? 3 : periodId ? 2 : 1
  const noBlock = controls ? controls.bloquants === 0 : false

  return (
    <div className="space-y-6">
      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {/* En-tête + stepper */}
      <div className="bg-surface rounded-xl p-6 border border-border shadow-xs">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-6 border-b border-border/80">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-headline-lg font-headline-lg text-ink font-extrabold tracking-tight">Cycle de paie — {periode}</h1>
              {closed
                ? <span className="inline-flex items-center gap-1 bg-success text-white px-2.5 py-0.5 rounded-full text-xs font-bold"><Icon name="check_circle" className="text-xs" />Clôturé</span>
                : periodId && <span className="inline-flex items-center gap-1 bg-secondary text-on-secondary px-2.5 py-0.5 rounded-full text-xs font-bold"><Icon name="sync" className="text-xs" />{payslips ? 'En cours de revue' : 'Cycle ouvert'}</span>}
            </div>
            <p className="font-body-md text-muted mt-1 flex flex-wrap items-center gap-2">
              <span>{societe}</span><span>•</span>
              <span className="font-semibold text-ink">{employees.length} salarié{employees.length > 1 ? 's' : ''} éligible{employees.length > 1 ? 's' : ''}</span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Sélecteur de période toujours visible : changer de mois recharge le cycle
                de ce mois (ou propose de l'ouvrir). L'utilisateur n'est jamais bloqué. */}
            <label className="flex items-center gap-1.5" title="Période de paie">
              <Icon name="calendar_today" className="text-muted text-[18px]" />
              <select value={mois} onChange={(e) => setMois(Number(e.target.value))} className="px-2.5 py-2 text-label-md bg-white rounded-lg border border-border focus:border-secondary focus:ring-2 focus:ring-secondary/20 outline-none">
                {MOIS.slice(1).map((m, i) => <option key={i} value={i + 1}>{m}</option>)}</select>
            </label>
            <input type="number" value={annee} onChange={(e) => setAnnee(Number(e.target.value))} aria-label="Année" className="w-20 px-2.5 py-2 text-label-md bg-white rounded-lg border border-border focus:border-secondary focus:ring-2 focus:ring-secondary/20 outline-none" />
            {periodId && <button onClick={calculate} disabled={busy === 'calc'} className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg text-label-md font-bold hover:bg-primary-container transition-colors shadow-sm disabled:opacity-50">
              <Icon name="calculate" className="text-base" /><span>{busy === 'calc' ? 'Calcul…' : payslips ? 'Recalculer tout' : 'Calculer'}</span></button>}
          </div>
        </div>
        <div className="pt-6 grid grid-cols-1 md:grid-cols-4 gap-4">
          <StepCard n={1} titre="Préparation & Variables" sous="Heures supp, primes" state={step > 1 ? 'done' : 'active'} />
          <StepCard n={2} titre="Calcul automatique" sous={payslips ? `${payslips.length} bulletins générés` : 'En attente'} state={step > 2 ? 'done' : step === 2 ? 'active' : 'todo'} />
          <StepCard n={3} titre="Contrôles & Validation" sous="Audit légal Bénin" state={step > 3 ? 'done' : step === 3 ? 'active' : 'todo'} />
          <StepCard n={4} titre="Décaissement & Clôture" sous="Virements, MoMo & clôture" state={closed ? 'active' : 'todo'} />
        </div>
      </div>

      {/* Setup période (avant ouverture) : le mois/année se choisit dans l'en-tête.
          Ici on confirme simplement l'ouverture du cycle pour la période sélectionnée. */}
      {!periodId && (
        <div className="bg-surface rounded-xl p-6 border border-border shadow-xs flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-[12rem]">
            <p className="text-subtitle-md font-bold text-ink">Aucun cycle ouvert pour {periode}</p>
            <p className="text-label-md text-muted mt-0.5">Ouvrez la période pour saisir les variables et calculer les bulletins. Changez de mois dans l'en-tête ci-dessus.</p>
          </div>
          <button onClick={openPeriod} disabled={busy === 'open'} className="inline-flex items-center gap-2 px-4 py-2.5 bg-secondary-fixed text-ink font-extrabold rounded-xl hover:bg-secondary-fixed-dim shadow-sm disabled:opacity-50">
            <Icon name="event_available" className="text-[18px]" />{busy === 'open' ? 'Ouverture…' : `Ouvrir la période ${periode}`}</button>
        </div>
      )}

      {/* Variables */}
      {periodId && !closed && (
        <div className="bg-surface rounded-xl p-6 border border-border shadow-xs">
          <button onClick={() => setShowVars((v) => !v)} className="flex items-center gap-2 text-subtitle-md font-bold text-ink">
            <Icon name={showVars ? 'expand_less' : 'expand_more'} /> Variables du mois <span className="text-muted font-normal text-label-md">(primes, heures sup — optionnel)</span>
          </button>
          {showVars && (() => {
            const sel = rubs.find((r) => r.code === vr.code)
            const isHS = vr.code === 'heures_sup'
            const assiettes = sel ? [sel.soumis_cnss && 'CNSS', sel.soumis_its && 'ITS', sel.soumis_vps && 'VPS'].filter(Boolean) : []
            const horsCnss = sel && !sel.soumis_cnss && sel.nature === 'gain'
            return (
              <div className="mt-4 space-y-2">
                <div className="flex flex-wrap items-end gap-3">
                  <label className="space-y-1.5 min-w-[160px] flex-1"><span className="block text-label-lg font-semibold text-ink">Salarié</span>
                    <select value={vr.employee_id} onChange={(e) => setVr({ ...vr, employee_id: e.target.value })} className="w-full px-3 py-2.5 text-body-md bg-white rounded-xl border border-border outline-none focus:border-secondary">
                      <option value="">—</option>{employees.map((e) => <option key={e.id} value={e.id}>{e.nom}</option>)}</select></label>
                  <label className="space-y-1.5 min-w-[180px]"><span className="block text-label-lg font-semibold text-ink">Rubrique</span>
                    <select value={vr.code} onChange={(e) => setVr({ ...vr, code: e.target.value })} className="w-full px-3 py-2.5 text-body-md bg-white rounded-xl border border-border outline-none focus:border-secondary">
                      {rubs.map((r) => <option key={r.code} value={r.code}>{r.libelle}</option>)}</select></label>
                  {isHS ? (
                    <>
                      <label className="space-y-1.5 w-24"><span className="block text-label-lg font-semibold text-ink">Heures</span>
                        <input type="number" value={vr.hours} onChange={(e) => setVr({ ...vr, hours: e.target.value })} className="w-full px-3 py-2.5 text-body-md bg-white rounded-xl border border-border outline-none focus:border-secondary" /></label>
                      <label className="space-y-1.5 w-40"><span className="block text-label-lg font-semibold text-ink">Majoration</span>
                        <select value={vr.majoration} onChange={(e) => setVr({ ...vr, majoration: e.target.value })} className="w-full px-3 py-2.5 text-body-md bg-white rounded-xl border border-border outline-none focus:border-secondary">
                          <option value="0.12">+12% (41e-48e h)</option><option value="0.35">+35% (au-delà 48e)</option>
                          <option value="0.50">+50% (dim./férié, nuit)</option><option value="1">+100% (nuit dim./férié)</option></select></label>
                    </>
                  ) : (
                    <label className="space-y-1.5 w-36"><span className="block text-label-lg font-semibold text-ink">Montant</span>
                      <input type="number" value={vr.montant} onChange={(e) => setVr({ ...vr, montant: e.target.value })} className="w-full px-3 py-2.5 text-body-md bg-white rounded-xl border border-border outline-none focus:border-secondary" /></label>
                  )}
                  <button onClick={addVariable} disabled={busy === 'var' || !vr.employee_id || (isHS ? !vr.hours : !vr.montant)} className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-secondary-fixed text-ink font-bold rounded-xl hover:bg-secondary-fixed-dim disabled:opacity-50"><Icon name="add" className="text-[18px]" />Ajouter</button>
                </div>
                {sel && (
                  <p className="text-label-md text-muted flex items-center gap-1.5">
                    <Icon name="info" className="text-[15px] text-secondary" />
                    {sel.nature === 'retenue_net' ? 'Prélevée sur le net à payer (hors cotisations/impôt).'
                      : sel.nature === 'retenue_brut' ? 'Réduit le brut et les assiettes (retenue).'
                      : <>Soumise à : <span className="font-semibold text-ink">{assiettes.join(' · ') || 'aucune assiette'}</span>{horsCnss && <span className="text-success font-semibold"> — exonérée CNSS (remboursement de frais)</span>}</>}
                  </p>
                )}
              </div>
            )
          })()}
        </div>
      )}

      {/* KPIs (après calcul) */}
      {kpis && (
        <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <Kpi label="Bulletins générés" value={`${kpis.n} / ${employees.length}`} icon="description" foot="100% calculés" footTone="text-success" />
          <Kpi label="Masse salariale brute" value={fcfa(kpis.brut).replace(' FCFA', '')} unit="FCFA" icon="account_balance_wallet" foot="Cumul brut du cycle" footTone="text-secondary" />
          <Kpi label="Net à payer global" value={fcfa(kpis.net).replace(' FCFA', '')} unit="FCFA" icon="payments" foot="À décaisser" footTone="text-muted" />
          <Kpi label="Retenue ITS & VPS" value={fcfa(kpis.its).replace(' FCFA', '')} unit="FCFA" icon="receipt" foot="Déclaration DGI (le 10)" footTone="text-warning" />
        </section>
      )}

      {/* Contrôles réglementaires */}
      {controls && (
        <section className="bg-surface rounded-xl border border-border p-6 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-border">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-success/10 text-success flex items-center justify-center"><Icon name="verified_user" className="text-xl" /></div>
              <div>
                <h2 className="text-subtitle-lg font-subtitle-lg text-ink font-bold">Contrôles réglementaires et conformité fiscale DGI &amp; CNSS</h2>
                <p className="text-xs text-muted">Vérification sur les {kpis?.n ?? 0} fiches de salaire générées</p>
              </div>
            </div>
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold ${noBlock ? 'bg-success/10 border border-success/30 text-success' : 'bg-danger/10 border border-danger/30 text-danger'}`}>
              <Icon name={noBlock ? 'check_circle' : 'error'} className="text-base" />{noBlock ? 'Aucune anomalie bloquante' : `${controls.bloquants} anomalie(s) bloquante(s)`}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
            <Controle titre="Barème ITS DGI" desc="Tranches progressives appliquées avec abattements" tag="Conforme" />
            <Controle titre="Cotisations CNSS Bénin" desc="Parts patronale (6,4 % + PF + AT/MP) & salariale (3,6 %) — sans plafond d'assiette" tag="Conforme" />
            <Controle titre="Seuil SMIG Bénin" desc="Seuil plancher de 52 000 FCFA respecté" tag="Vérifié" />
            <Controle titre="Moteur déterministe" desc="Calcul reproductible et versionné" tag="Certifié" />
          </div>
          {controls.anomalies.length > 0 && (
            <ul className="mt-4 flex flex-col gap-2">
              {controls.anomalies.map((a, i) => (
                <li key={i} className="p-3 rounded-lg bg-warm-sand/20 border border-warm-sand/50 flex items-center gap-2.5 text-xs">
                  <Icon name={a.gravite === 'bloquant' ? 'error' : 'info'} className={`text-lg ${a.gravite === 'bloquant' ? 'text-danger' : 'text-warning'}`} />
                  <span><strong className="font-bold text-ink">{a.gravite === 'bloquant' ? 'Bloquant' : 'Observation'} :</strong> {a.nom ? a.nom + ' — ' : ''}{a.message ?? a.libelle ?? a.code ?? ''}</span>
                </li>
              ))}
            </ul>
          )}
          {runId && !closed && (
            <div className="mt-4">
              <button onClick={close} disabled={busy === 'close' || controls.bloquants > 0} className="inline-flex items-center gap-2 px-5 py-2.5 bg-secondary-fixed text-ink font-extrabold rounded-xl hover:bg-secondary-fixed-dim shadow-sm disabled:opacity-50">
                <Icon name="lock" className="text-[18px]" />{controls.bloquants > 0 ? 'Clôture bloquée (corriger les anomalies)' : busy === 'close' ? 'Clôture…' : 'Valider & clôturer'}</button>
            </div>
          )}
        </section>
      )}

      {/* Bulletins */}
      {payslips && (
        <section className="bg-surface rounded-xl border border-border shadow-xs overflow-hidden">
          <div className="p-4 px-6 border-b border-border flex items-center gap-3">
            <h3 className="text-subtitle-lg font-subtitle-lg text-ink font-bold">Bulletins du cycle</h3>
            <span className="px-2.5 py-0.5 rounded-full bg-primary text-on-primary text-label-md font-bold">Tous ({payslips.length})</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wider">
                <th className="py-3 px-6">Salarié</th><th className="py-3 px-4 text-right">Brut</th><th className="py-3 px-4 text-right">Retenues</th>
                <th className="py-3 px-4 text-right">Coût employeur</th><th className="py-3 px-6 text-right">Net à payer</th><th className="py-3 px-4 text-center">Bulletin</th>
              </tr></thead>
              <tbody className="divide-y divide-border text-body-md text-ink">
                {payslips.map((p, i) => {
                  // Retenues = brut − net à payer : la ligne se réconcilie TOUJOURS avec
                  // la colonne « Net à payer » (p.net = net_a_payer, avance incluse). Sinon,
                  // avec une avance, brut − retenues ≠ net affiché → le non-expert doute.
                  const ret = (p.detail?.brut ?? p.brut) - p.net
                  return (
                    <tr key={i} className="hover:bg-primary-fixed/20 transition-colors">
                      <td className="py-3.5 px-6"><div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">{p.nom.slice(0, 2).toUpperCase()}</div>
                        <div className="flex flex-col"><span className="font-bold text-ink flex items-center gap-1.5">{p.nom}{p.verrouille && <Icon name="lock" className="text-[13px] text-muted" />}</span>
                          <span className="text-label-md text-muted font-mono">{p.matricule ?? ''}</span></div></div></td>
                      <td className="py-3.5 px-4 text-right tabular-nums text-muted">{fcfa(p.brut)}</td>
                      <td className="py-3.5 px-4 text-right tabular-nums text-danger">- {fcfa(ret)}</td>
                      <td className="py-3.5 px-4 text-right tabular-nums text-muted">{fcfa(p.cout_employeur)}</td>
                      <td className="py-3.5 px-6 text-right tabular-nums font-extrabold text-secondary">{fcfa(p.net)}</td>
                      <td className="py-3.5 px-4 text-center">
                        <button onClick={() => setBulletin(p)} className="inline-flex items-center gap-1 text-secondary font-bold text-label-md hover:underline"><Icon name="receipt_long" className="text-[16px]" /> Voir</button></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Décaissement — disponible une fois le cycle clôturé (étape 4) */}
      {closed && payslips && (
        <section className="bg-surface rounded-xl border border-border p-6 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-border">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-secondary/10 text-secondary flex items-center justify-center"><Icon name="account_balance_wallet" className="text-xl" /></div>
              <div>
                <h2 className="text-subtitle-lg font-subtitle-lg text-ink font-bold">Décaissement des salaires</h2>
                <p className="text-xs text-muted">Virements, Mobile Money (MTN/Moov) & espèces — net à payer de chaque salarié</p>
              </div>
            </div>
            {!payout && (
              <button onClick={decaisser} disabled={busy === 'payout'} className="inline-flex items-center gap-2 px-5 py-2.5 bg-secondary text-on-secondary font-extrabold rounded-xl hover:bg-secondary/90 shadow-sm disabled:opacity-50">
                <Icon name="send" className="text-[18px]" />{busy === 'payout' ? 'Préparation…' : 'Lancer le décaissement'}</button>
            )}
          </div>
          {!payout ? (
            <p className="mt-4 text-body-md text-muted">
              Prépare l'ordre de paiement de <span className="font-bold text-ink">{fcfa(kpis?.net)}</span> pour {kpis?.n ?? 0} salarié{(kpis?.n ?? 0) > 1 ? 's' : ''}.
              Le Mobile Money est transmis à la passerelle ; les virements et espèces sont générés « à envoyer » pour traitement par la banque.
            </p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wider">
                  <th className="py-3 px-6">Salarié</th><th className="py-3 px-4">Méthode</th><th className="py-3 px-4 text-right">Montant</th><th className="py-3 px-4 text-center">Statut</th>
                </tr></thead>
                <tbody className="divide-y divide-border text-body-md text-ink">
                  {payout.map((it, i) => (
                    <tr key={i}>
                      <td className="py-3 px-6 font-bold text-ink">{it.nom}</td>
                      <td className="py-3 px-4 capitalize text-muted">{it.methode.replace('_', ' ')}</td>
                      <td className="py-3 px-4 text-right tabular-nums font-extrabold text-secondary">{fcfa(it.montant)}</td>
                      <td className="py-3 px-4 text-center">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold ${
                          it.statut === 'envoye' || it.statut === 'confirme' ? 'bg-success/10 text-success'
                          : it.statut === 'echec' ? 'bg-danger/10 text-danger' : 'bg-warm-sand/30 text-warning'}`}>
                          <Icon name={it.statut === 'envoye' || it.statut === 'confirme' ? 'check_circle' : it.statut === 'echec' ? 'error' : 'schedule'} className="text-sm" />
                          {it.statut === 'a_envoyer' ? 'À envoyer' : it.statut === 'envoye' ? 'Envoyé' : it.statut === 'confirme' ? 'Confirmé' : it.statut === 'echec' ? 'Échec' : it.statut}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-label-md text-muted flex items-center gap-1.5"><Icon name="info" className="text-[15px] text-secondary" />Les lignes « à envoyer » (virement/espèces) sont à exécuter via la banque ; le Mobile Money est transmis à la passerelle. Ordre idempotent : relancer ne double jamais un paiement.</p>
            </div>
          )}
        </section>
      )}

      {bulletin && <BulletinModal payslip={bulletin} mois={mois} annee={annee} societe={societe} onClose={() => setBulletin(null)} />}
    </div>
  )
}
