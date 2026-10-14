import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Controls, type Employee, type Payslip } from '../api'
import { Button, Field, Spinner } from '../ui'

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

  useEffect(() => { api.employees(cid).then((r) => setEmployees(r.employes)).catch(() => undefined) }, [cid])

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

  const selectStyle = { width: '100%', padding: '12px 14px', borderRadius: 10, border: '1px solid var(--line)', fontFamily: 'inherit', fontSize: '1rem' }

  return (
    <div>
      <h2>Paie</h2>
      {error && <div className="error" style={{ marginBottom: 12 }}>{error}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="row" style={{ gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ width: 100 }}><Field label="Mois" type="number" min={1} max={12} value={String(mois)} onChange={(e) => setMois(Number(e.target.value))} /></div>
          <div style={{ width: 120 }}><Field label="Année" type="number" value={String(annee)} onChange={(e) => setAnnee(Number(e.target.value))} /></div>
          <Button onClick={openPeriod} disabled={busy === 'open'}>{busy === 'open' ? '…' : 'Ouvrir la période'}</Button>
          {periodId && <span className="badge" style={{ background: 'var(--teal-600)' }}>période ouverte</span>}
        </div>
      </div>

      {periodId && !closed && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Variables (optionnel)</h3>
          <div className="row" style={{ gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div style={{ minWidth: 170, flex: 1 }}>
              <div className="field"><label>Salarié</label>
                <select value={vr.employee_id} onChange={(e) => setVr({ ...vr, employee_id: e.target.value })} style={selectStyle}>
                  <option value="">—</option>
                  {employees.map((e) => <option key={e.id} value={e.id}>{e.nom}</option>)}
                </select>
              </div>
            </div>
            <div style={{ width: 140 }}><Field label="Type" value={vr.type} onChange={(e) => setVr({ ...vr, type: e.target.value })} /></div>
            <div style={{ width: 130 }}><Field label="Montant" type="number" value={vr.montant} onChange={(e) => setVr({ ...vr, montant: e.target.value })} /></div>
            <Button variant="ghost" onClick={addVariable} disabled={busy === 'var' || !vr.employee_id || !vr.montant}>Ajouter</Button>
          </div>
        </div>
      )}

      {periodId && (
        <div style={{ marginBottom: 16 }}>
          <Button onClick={calculate} disabled={busy === 'calc'}>{busy === 'calc' ? 'Calcul…' : 'Calculer la paie'}</Button>
        </div>
      )}

      {controls && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Contrôles</h3>
          <p style={{ marginBottom: 10 }}>
            <span className={controls.bloquants ? 'error' : 'muted'}>{controls.bloquants} bloquant(s)</span>
            {' · '}<span className="muted">{controls.avertissements} avertissement(s)</span>
          </p>
          {controls.anomalies.length > 0 && (
            <ul style={{ paddingLeft: 18, marginBottom: 12 }}>
              {controls.anomalies.map((a, i) => (
                <li key={i} style={{ marginBottom: 6 }}>
                  <span className="badge" style={{ background: a.gravite === 'bloquant' ? 'var(--danger)' : 'var(--alert)' }}>{a.gravite}</span>{' '}
                  {a.nom ? a.nom + ' — ' : ''}{a.message ?? a.libelle ?? a.code ?? ''}
                </li>
              ))}
            </ul>
          )}
          {runId && !closed && (
            <Button onClick={close} disabled={busy === 'close' || controls.bloquants > 0}>
              {controls.bloquants > 0 ? 'Clôture bloquée (corriger les anomalies)' : busy === 'close' ? 'Clôture…' : 'Valider et clôturer'}
            </Button>
          )}
          {closed && <span className="badge" style={{ background: 'var(--success)' }}>Clôturée</span>}
        </div>
      )}

      {busy === 'calc' && <div className="row"><Spinner /> <span className="muted">Calcul en cours…</span></div>}

      {payslips && (
        <div className="card">
          <h3>Bulletins <span className="badge">{payslips.length}</span></h3>
          <div className="list">
            {payslips.map((p, i) => (
              <div key={i} className="list-item" style={{ borderTop: i ? '1px solid var(--line)' : 'none', paddingTop: i ? 12 : 0 }}>
                <div><h3 style={{ margin: 0, fontSize: '.98rem' }}>{p.nom}</h3><span className="muted">brut {fcfa(p.brut)}</span></div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontWeight: 800, color: 'var(--teal-600)' }}>{fcfa(p.net)}</div>
                  {p.verrouille && <span className="muted" style={{ fontSize: '.74rem' }}>🔒 verrouillé</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
