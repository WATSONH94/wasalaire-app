import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Employee } from '../api'
import { Badge, Button, Card, Field, Icon } from '../stitch'

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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-subtitle-lg font-subtitle-lg text-ink">Équipe</h2>
          {list && <Badge tone="neutral">{list.length} {list.length > 1 ? 'salariés' : 'salarié'}</Badge>}
        </div>
        <Button variant="primary" icon={open ? 'close' : 'person_add'} onClick={() => setOpen((v) => !v)}>
          {open ? 'Fermer' : 'Ajouter un salarié'}
        </Button>
      </div>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {open && (
        <Card className="p-5">
          <form onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Matricule" value={form.matricule} onChange={(e) => setForm({ ...form, matricule: e.target.value })} required />
            <Field label="Nom complet" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} required />
            <Field label="Salaire de base (FCFA)" type="number" value={form.salaire_base} onChange={(e) => setForm({ ...form, salaire_base: e.target.value })} required />
            <Field label="N° CNSS (optionnel)" value={form.num_cnss} onChange={(e) => setForm({ ...form, num_cnss: e.target.value })} />
            {formError && <div className="sm:col-span-2 p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{formError}</div>}
            <div className="sm:col-span-2">
              <Button variant="primary" type="submit" disabled={busy} icon="check">{busy ? 'Enregistrement…' : 'Créer le salarié'}</Button>
            </div>
          </form>
        </Card>
      )}

      {list == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : list.length === 0 ? (
        <Card className="p-10 text-center">
          <Icon name="group_off" className="text-[40px] text-outline-variant" />
          <p className="text-muted mt-2">Aucun salarié. Ajoutez votre premier collaborateur.</p>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-border text-label-lg font-bold text-muted">
                  <th className="py-3 px-6">Salarié</th>
                  <th className="py-3 px-4">Matricule</th>
                  <th className="py-3 px-6 text-right">Salaire de base</th>
                  <th className="py-3 px-4 w-16"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-body-md text-ink">
                {list.map((e) => (
                  <tr key={e.id} className="hover:bg-primary-fixed/20 transition-colors">
                    <td className="py-3.5 px-6">
                      <Link to={`/c/${cid}/salaries/${e.id}`} className="flex items-center gap-3 group">
                        <div className="w-8 h-8 rounded-lg bg-secondary/10 text-secondary flex items-center justify-center font-bold text-xs">
                          {e.nom.slice(0, 2).toUpperCase()}
                        </div>
                        <span className="font-bold text-ink group-hover:text-secondary transition-colors">{e.nom}</span>
                      </Link>
                    </td>
                    <td className="py-3.5 px-4 text-label-md text-muted tabular-nums">{e.matricule}</td>
                    <td className="py-3.5 px-6 text-right font-semibold tabular-nums">{fcfa(e.salaire_base ?? undefined)}</td>
                    <td className="py-3.5 px-4 text-center">
                      <Link to={`/c/${cid}/salaries/${e.id}`} className="text-outline-variant hover:text-secondary" title="Ouvrir la fiche">
                        <Icon name="arrow_forward" className="text-[18px]" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
