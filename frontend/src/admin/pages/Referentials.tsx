import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, fcfa, type RegChange, type RegReferentials } from '../../api'
import { Badge, Button, Card, Field, Icon, PageHeader } from '../../stitch'
import { useAuth } from '../../auth'

const STATUT_TONE: Record<string, 'neutral' | 'warning' | 'secondary' | 'success' | 'danger'> = {
  proposee: 'warning', validee: 'secondary', publiee: 'success', rejetee: 'danger',
}
const STATUT_LABEL: Record<string, string> = {
  proposee: 'Proposée', validee: 'Validée', publiee: 'Publiée', rejetee: 'Rejetée',
}

export default function Referentials() {
  const { session } = useAuth()
  const canWrite = session?.platform_role === 'conformite' || session?.platform_role === 'super_admin'
  const [ref, setRef] = useState<RegReferentials | null>(null)
  const [changes, setChanges] = useState<RegChange[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ cible_code: '', valeur: '', date_effet: '', source: '', note: '' })

  function load() {
    api.adminReferentials().then(setRef).catch((e) => setError(e instanceof ApiError ? (e.status === 403 ? 'Réservé à la conformité / super-admin.' : e.message) : 'Erreur réseau'))
    api.adminRegChanges().then((r) => setChanges(r.changes)).catch(() => undefined)
  }
  useEffect(load, [])

  async function act(id: string, fn: () => Promise<unknown>) {
    setBusy(id); setError(null)
    try { await fn(); load() } catch (e) { setError(e instanceof ApiError ? e.message : 'Erreur réseau') } finally { setBusy(null) }
  }

  async function propose(e: FormEvent) {
    e.preventDefault(); setBusy('form'); setError(null)
    try {
      await api.adminRegPropose({ type: 'rate', cible_code: form.cible_code.trim(), payload: { valeur: Number(form.valeur) }, date_effet: form.date_effet, source: form.source.trim(), note: form.note.trim() || undefined })
      setForm({ cible_code: '', valeur: '', date_effet: '', source: '', note: '' }); setShowForm(false); load()
    } catch (e) { setError(e instanceof ApiError ? e.message : 'Erreur réseau') } finally { setBusy(null) }
  }

  return (
    <>
      <PageHeader
        title="Référentiels réglementaires"
        subtitle="Barèmes DGI/CNSS versionnés (datés d’effet). Toute modification suit un workflow validé — aucune valeur n’est inventée."
        actions={canWrite && <Button variant="primary" icon="add" onClick={() => setShowForm((v) => !v)}>Proposer une modification</Button>}
      />

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {showForm && canWrite && (
        <Card className="p-5">
          <form onSubmit={propose} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Code du taux (rate_table)" value={form.cible_code} onChange={(e) => setForm({ ...form, cible_code: e.target.value })} required placeholder="ex. cnss_plafond" />
            <Field label="Nouvelle valeur" type="number" step="any" value={form.valeur} onChange={(e) => setForm({ ...form, valeur: e.target.value })} required />
            <Field label="Date d’effet" type="date" value={form.date_effet} onChange={(e) => setForm({ ...form, date_effet: e.target.value })} required />
            <Field label="Source juridique (obligatoire)" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} required placeholder="ex. Loi de finances 2026, art. X" />
            <Field label="Note (optionnel)" className="sm:col-span-2" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
            <div className="sm:col-span-2"><Button variant="primary" type="submit" disabled={busy === 'form'} icon="send">{busy === 'form' ? 'Envoi…' : 'Soumettre la proposition'}</Button></div>
          </form>
        </Card>
      )}

      {/* Propositions / workflow */}
      <Card className="overflow-hidden">
        <div className="p-4 px-6 border-b border-border flex items-center gap-3">
          <h3 className="text-subtitle-md font-bold text-ink">Propositions de modification</h3>
          {changes && <Badge tone="neutral">{changes.length}</Badge>}
        </div>
        {changes == null ? <div className="p-6 text-muted flex items-center gap-2"><span className="spinner" /> Chargement…</div>
          : changes.length === 0 ? <div className="p-8 text-center text-muted">Aucune proposition.</div> : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted">
                  <th className="py-3 px-6">Cible</th><th className="py-3 px-4">Valeur</th><th className="py-3 px-4">Date d’effet</th>
                  <th className="py-3 px-4">Source</th><th className="py-3 px-4">Statut</th><th className="py-3 px-6 text-right">Actions</th>
                </tr></thead>
                <tbody className="divide-y divide-border text-body-md text-ink">
                  {changes.map((c) => (
                    <tr key={c.id} className="hover:bg-primary-fixed/20">
                      <td className="py-3 px-6 font-bold font-mono text-label-md">{c.cible_code}</td>
                      <td className="py-3 px-4 tabular-nums">{c.payload?.valeur != null ? fcfa(c.payload.valeur) : c.payload?.taux != null ? c.payload.taux + ' %' : '—'}</td>
                      <td className="py-3 px-4 text-label-md text-muted">{c.date_effet}</td>
                      <td className="py-3 px-4 text-label-md text-muted max-w-[14rem] truncate" title={c.source}>{c.source}</td>
                      <td className="py-3 px-4"><Badge tone={STATUT_TONE[c.statut] ?? 'neutral'}>{STATUT_LABEL[c.statut] ?? c.statut}</Badge></td>
                      <td className="py-3 px-6 text-right">
                        {canWrite && c.statut === 'proposee' && (
                          <div className="inline-flex gap-2">
                            <button disabled={busy === c.id} onClick={() => act(c.id, () => api.adminRegValidate(c.id))} className="text-secondary font-bold text-label-md hover:underline">Valider</button>
                            <button disabled={busy === c.id} onClick={() => act(c.id, () => api.adminRegReject(c.id))} className="text-danger font-bold text-label-md hover:underline">Rejeter</button>
                          </div>
                        )}
                        {canWrite && c.statut === 'validee' && (
                          <button disabled={busy === c.id} onClick={() => act(c.id, () => api.adminRegPublish(c.id))} className="text-success font-bold text-label-md hover:underline inline-flex items-center gap-1"><Icon name="publish" className="text-[16px]" /> Publier</button>
                        )}
                        {(c.statut === 'publiee' || c.statut === 'rejetee') && <span className="text-muted text-label-md">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Card>

      {/* Barèmes en vigueur */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <Card className="overflow-hidden">
          <div className="p-4 px-6 border-b border-border"><h3 className="text-subtitle-md font-bold text-ink">Taux & montants (rate_table)</h3></div>
          <div className="overflow-x-auto max-h-96 overflow-y-auto">
            <table className="w-full text-left border-collapse text-body-md">
              <thead className="sticky top-0"><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted">
                <th className="py-2 px-4">Code</th><th className="py-2 px-4 text-right">Valeur</th><th className="py-2 px-4">Effet</th></tr></thead>
              <tbody className="divide-y divide-border">
                {ref?.rates.map((r, i) => (
                  <tr key={i}><td className="py-2 px-4 font-mono text-label-md">{r.code}</td><td className="py-2 px-4 text-right tabular-nums">{fcfa(r.valeur)}</td><td className="py-2 px-4 text-label-md text-muted">{r.date_effet}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card className="overflow-hidden">
          <div className="p-4 px-6 border-b border-border"><h3 className="text-subtitle-md font-bold text-ink">Barème ITS (tax_bracket)</h3></div>
          <div className="overflow-x-auto max-h-96 overflow-y-auto">
            <table className="w-full text-left border-collapse text-body-md">
              <thead className="sticky top-0"><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted">
                <th className="py-2 px-4">Tranche</th><th className="py-2 px-4 text-right">Taux</th><th className="py-2 px-4">Effet</th></tr></thead>
              <tbody className="divide-y divide-border">
                {ref?.brackets.map((b, i) => (
                  <tr key={i}><td className="py-2 px-4 tabular-nums text-label-md">{fcfa(b.tranche_min)} – {b.tranche_max != null ? fcfa(b.tranche_max) : '∞'}</td><td className="py-2 px-4 text-right tabular-nums">{b.taux} %</td><td className="py-2 px-4 text-label-md text-muted">{b.date_effet}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  )
}
