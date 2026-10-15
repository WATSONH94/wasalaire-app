import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Company, type Controls, type Employee, type Payslip } from '../api'
import { Badge, Button, Card, Field, Icon, Select } from '../stitch'
import BulletinModal from '../components/BulletinModal'

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
  const [vr, setVr] = useState({ employee_id: '', type: 'Prime', montant: '' })
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [closed, setClosed] = useState(false)
  const [bulletin, setBulletin] = useState<Payslip | null>(null)
  const [company, setCompany] = useState<Company | null>(null)

  useEffect(() => { api.employees(cid).then((r) => setEmployees(r.employes)).catch(() => undefined) }, [cid])
  useEffect(() => { api.companies().then((r) => setCompany(r.companies.find((c) => c.id === cid) ?? null)).catch(() => undefined) }, [cid])

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
    await api.addVariable({ company_id: cid, period_id: periodId, employee_id: vr.employee_id, type: vr.type, montant: Number(vr.montant) })
    setVr({ ...vr, montant: '' })
  })
  const calculate = () => run('calc', async () => {
    if (!periodId) return
    const periode = `${annee}-${String(mois).padStart(2, '0')}-01`
    const r = await api.calculate({ company_id: cid, period_id: periodId, periode })
    setRunId(r.run_id)
    setControls(await api.controls(r.run_id))
    setPayslips((await api.payslips(r.run_id)).bulletins)
  })
  const close = () => run('close', async () => {
    if (!runId || !periodId) return
    await api.closeRun(runId, periodId); setClosed(true)
    setPayslips((await api.payslips(runId)).bulletins)
  })

  // Étapes du cycle (indicateur visuel)
  const step = closed ? 4 : payslips ? 3 : periodId ? 2 : 1
  const STEPS = ['Ouvrir', 'Variables', 'Calculer', 'Clôturer']

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h2 className="text-subtitle-lg font-subtitle-lg text-ink">Cycle de paie</h2>
        {periodId && !closed && <Badge tone="secondary" icon="lock_open">Période ouverte</Badge>}
        {closed && <Badge tone="success" icon="check_circle">Clôturée</Badge>}
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-2">
        {STEPS.map((s, i) => {
          const n = i + 1
          const done = n < step
          const active = n === step
          return (
            <div key={s} className="flex items-center gap-2 flex-1">
              <div className={`flex items-center gap-2 ${active ? 'text-secondary' : done ? 'text-success' : 'text-muted'}`}>
                <div className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs ${
                  done ? 'bg-success text-white' : active ? 'bg-secondary text-white' : 'bg-surface-container text-muted'
                }`}>
                  {done ? <Icon name="check" className="text-[16px]" /> : n}
                </div>
                <span className="text-label-md font-bold hidden sm:inline">{s}</span>
              </div>
              {i < STEPS.length - 1 && <div className={`h-0.5 flex-1 rounded ${done ? 'bg-success' : 'bg-border'}`} />}
            </div>
          )
        })}
      </div>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {/* 1. Période */}
      <Card className="p-5">
        <div className="flex flex-wrap items-end gap-4">
          <Field label="Mois" type="number" min={1} max={12} className="w-24" value={String(mois)} onChange={(e) => setMois(Number(e.target.value))} />
          <Field label="Année" type="number" className="w-32" value={String(annee)} onChange={(e) => setAnnee(Number(e.target.value))} />
          <Button variant="primary" icon="event_available" onClick={openPeriod} disabled={busy === 'open'}>
            {busy === 'open' ? 'Ouverture…' : 'Ouvrir la période'}
          </Button>
        </div>
      </Card>

      {/* 2. Variables */}
      {periodId && !closed && (
        <Card className="p-5 flex flex-col gap-3">
          <h3 className="text-subtitle-md font-bold text-ink">Variables du mois <span className="text-muted font-normal text-label-md">(optionnel)</span></h3>
          <div className="flex flex-wrap items-end gap-3">
            <Select label="Salarié" className="min-w-[180px] flex-1" value={vr.employee_id} onChange={(e) => setVr({ ...vr, employee_id: e.target.value })}>
              <option value="">—</option>
              {employees.map((e) => <option key={e.id} value={e.id}>{e.nom}</option>)}
            </Select>
            <Field label="Type" className="w-36" value={vr.type} onChange={(e) => setVr({ ...vr, type: e.target.value })} />
            <Field label="Montant" type="number" className="w-36" value={vr.montant} onChange={(e) => setVr({ ...vr, montant: e.target.value })} />
            <Button icon="add" onClick={addVariable} disabled={busy === 'var' || !vr.employee_id || !vr.montant}>Ajouter</Button>
          </div>
        </Card>
      )}

      {/* 3. Calcul */}
      {periodId && (
        <div>
          <Button variant="primary" icon="calculate" onClick={calculate} disabled={busy === 'calc'}>
            {busy === 'calc' ? 'Calcul en cours…' : 'Calculer la paie'}
          </Button>
        </div>
      )}

      {/* Contrôles */}
      {controls && (
        <Card className="p-5 flex flex-col gap-3">
          <h3 className="text-subtitle-md font-bold text-ink">Contrôles</h3>
          <div className="flex items-center gap-2">
            <Badge tone={controls.bloquants ? 'danger' : 'success'} icon={controls.bloquants ? 'error' : 'check_circle'}>
              {controls.bloquants} bloquant{controls.bloquants > 1 ? 's' : ''}
            </Badge>
            <Badge tone={controls.avertissements ? 'warning' : 'neutral'}>
              {controls.avertissements} avertissement{controls.avertissements > 1 ? 's' : ''}
            </Badge>
          </div>
          {controls.anomalies.length > 0 && (
            <ul className="flex flex-col gap-2">
              {controls.anomalies.map((a, i) => (
                <li key={i} className="flex items-start gap-2 text-body-md">
                  <Badge tone={a.gravite === 'bloquant' ? 'danger' : 'warning'}>{a.gravite}</Badge>
                  <span className="text-ink">{a.nom ? a.nom + ' — ' : ''}{a.message ?? a.libelle ?? a.code ?? ''}</span>
                </li>
              ))}
            </ul>
          )}
          {runId && !closed && (
            <div>
              <Button variant="primary" icon="lock" onClick={close} disabled={busy === 'close' || controls.bloquants > 0}>
                {controls.bloquants > 0 ? 'Clôture bloquée (corriger les anomalies)' : busy === 'close' ? 'Clôture…' : 'Valider et clôturer'}
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* Bulletins */}
      {payslips && (
        <Card className="overflow-hidden">
          <div className="p-4 px-6 border-b border-border flex items-center gap-3">
            <h3 className="text-subtitle-md font-bold text-ink">Bulletins</h3>
            <Badge tone="neutral">{payslips.length}</Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-border text-label-lg font-bold text-muted">
                  <th className="py-3 px-6">Salarié</th>
                  <th className="py-3 px-4 text-right">Brut</th>
                  <th className="py-3 px-4 text-right">Coût employeur</th>
                  <th className="py-3 px-6 text-right">Net à payer</th>
                  <th className="py-3 px-4 text-center w-28">Bulletin</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-body-md text-ink">
                {payslips.map((p, i) => (
                  <tr key={i} className="hover:bg-primary-fixed/20 transition-colors">
                    <td className="py-3.5 px-6 font-bold flex items-center gap-2">
                      {p.nom}
                      {p.verrouille && <Icon name="lock" className="text-[14px] text-muted" />}
                    </td>
                    <td className="py-3.5 px-4 text-right tabular-nums text-muted">{fcfa(p.brut)}</td>
                    <td className="py-3.5 px-4 text-right tabular-nums text-muted">{fcfa(p.cout_employeur)}</td>
                    <td className="py-3.5 px-6 text-right tabular-nums font-extrabold text-secondary">{fcfa(p.net)}</td>
                    <td className="py-3.5 px-4 text-center">
                      <button onClick={() => setBulletin(p)} className="inline-flex items-center gap-1 text-secondary font-bold text-label-md hover:underline" title="Voir le bulletin">
                        <Icon name="receipt_long" className="text-[16px]" /> Voir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {bulletin && (
        <BulletinModal
          payslip={bulletin}
          mois={mois}
          annee={annee}
          societe={company?.raison_sociale ?? company?.nom}
          onClose={() => setBulletin(null)}
        />
      )}
    </div>
  )
}
