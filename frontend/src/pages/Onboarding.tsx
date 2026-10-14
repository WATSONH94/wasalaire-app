import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError, type OrgNode } from '../api'
import { Button, Card, Field, Icon, PageHeader } from '../stitch'

const NODE_LABEL: Record<string, string> = {
  cabinet: 'Cabinet', client: 'Client', groupe: 'Groupe', societe: 'Société',
}

export default function Onboarding() {
  const nav = useNavigate()
  const [nodes, setNodes] = useState<OrgNode[] | null>(null)
  const [parent, setParent] = useState('')
  const [raison, setRaison] = useState('')
  const [ifu, setIfu] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.adminNodes()
      .then((r) => { setNodes(r.nodes); if (r.nodes[0]) setParent(r.nodes[0].id) })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }, [])

  async function submit(e: FormEvent) {
    e.preventDefault(); setError(null); setBusy(true)
    try {
      const r = await api.createCompany(parent, raison.trim(), ifu.trim() || null)
      nav(`/c/${r.company_id}`, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur réseau')
    } finally { setBusy(false) }
  }

  return (
    <>
      <PageHeader title="Créer une société" subtitle="Ajoutez une société à votre espace de travail pour démarrer la paie." />

      <div className="max-w-2xl">
        {nodes == null ? (
          <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
        ) : nodes.length === 0 ? (
          <Card className="p-8 text-center flex flex-col items-center gap-3">
            <div className="w-16 h-16 rounded-2xl bg-warning/10 text-warning flex items-center justify-center">
              <Icon name="workspaces" className="text-[32px]" />
            </div>
            <h2 className="text-subtitle-lg font-subtitle-lg text-ink">Aucun espace de travail</h2>
            <p className="text-body-md text-muted max-w-md">
              Vous n’êtes administrateur d’aucun cabinet ou entreprise. La création du premier espace
              se fait à l’ouverture de votre compte. Contactez votre administrateur si besoin.
            </p>
          </Card>
        ) : (
          <Card className="p-6">
            <form onSubmit={submit} className="flex flex-col gap-5">
              {error && (
                <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold flex items-start gap-2">
                  <Icon name="error" className="text-[18px] mt-0.5" /> <span>{error}</span>
                </div>
              )}

              {nodes.length > 1 && (
                <label className="block space-y-1.5">
                  <span className="block text-label-lg font-semibold text-ink">Rattacher à</span>
                  <select
                    value={parent}
                    onChange={(e) => setParent(e.target.value)}
                    className="w-full px-3 py-2.5 text-body-md text-ink bg-white rounded-xl border border-border focus:border-secondary focus:ring-2 focus:ring-secondary/20 outline-none"
                  >
                    {nodes.map((n) => (
                      <option key={n.id} value={n.id}>{NODE_LABEL[n.type] ?? n.type} — {n.nom}</option>
                    ))}
                  </select>
                </label>
              )}
              {nodes.length === 1 && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-surface-container-low border border-border text-label-md">
                  <Icon name="workspaces" className="text-primary text-[18px]" />
                  <span className="text-muted">Rattachée à</span>
                  <span className="font-bold text-ink">{nodes[0].nom}</span>
                </div>
              )}

              <Field label="Raison sociale" value={raison} onChange={(e) => setRaison(e.target.value)} required placeholder="Ex. Novatech Cotonou SARL" autoFocus />
              <Field label="IFU (optionnel)" value={ifu} onChange={(e) => setIfu(e.target.value)} placeholder="13 chiffres" inputMode="numeric" />

              <div className="flex items-center gap-3">
                <Button variant="primary" type="submit" disabled={busy || !raison.trim()} icon="add_business">
                  {busy ? 'Création…' : 'Créer la société'}
                </Button>
                <Button type="button" variant="ghost" onClick={() => nav('/portefeuille')}>Annuler</Button>
              </div>
            </form>
          </Card>
        )}
      </div>
    </>
  )
}
