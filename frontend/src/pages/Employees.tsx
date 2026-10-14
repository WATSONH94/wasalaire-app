import { useEffect, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Employee } from '../api'
import { Button, Field, Spinner } from '../ui'

export default function Employees() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [list, setList] = useState<Employee[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ matricule: '', nom: '', salaire_base: '', num_cnss: '' })
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  function load() {
    setError(null)
    api.employees(cid)
      .then((r) => setList(r.employes))
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }
  useEffect(load, [cid])

  async function submit(e: FormEvent) {
    e.preventDefault(); setFormError(null); setBusy(true)
    try {
      await api.createEmployee({
        company_id: cid, matricule: form.matricule.trim(), nom: form.nom.trim(),
        salaire_base: Number(form.salaire_base), num_cnss: form.num_cnss.trim() || null,
      })
      setForm({ matricule: '', nom: '', salaire_base: '', num_cnss: '' }); setOpen(false); load()
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Erreur réseau')
    } finally { setBusy(false) }
  }

  if (error) return <div className="error">{error}</div>
  if (!list) return <div className="row"><Spinner /> <span className="muted">Chargement…</span></div>

  return (
    <div>
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Salariés <span className="badge">{list.length}</span></h2>
        <Button onClick={() => setOpen((v) => !v)}>{open ? 'Fermer' : 'Ajouter un salarié'}</Button>
      </div>

      {open && (
        <form onSubmit={submit} className="card" style={{ marginBottom: 16 }}>
          <Field label="Matricule" value={form.matricule} onChange={(e) => setForm({ ...form, matricule: e.target.value })} required />
          <Field label="Nom complet" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} required />
          <Field label="Salaire de base (FCFA)" type="number" value={form.salaire_base} onChange={(e) => setForm({ ...form, salaire_base: e.target.value })} required />
          <Field label="N° CNSS (optionnel)" value={form.num_cnss} onChange={(e) => setForm({ ...form, num_cnss: e.target.value })} />
          {formError && <div className="error" style={{ marginBottom: 10 }}>{formError}</div>}
          <Button type="submit" disabled={busy}>{busy ? 'Enregistrement…' : 'Créer'}</Button>
        </form>
      )}

      {list.length === 0 ? <p className="muted">Aucun salarié.</p> : (
        <div className="list">
          {list.map((e) => (
            <div key={e.id} className="card list-item">
              <div><h3>{e.nom}</h3><span className="muted">{e.matricule}</span></div>
              <div className="muted">{fcfa(e.salaire_base ?? undefined)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
