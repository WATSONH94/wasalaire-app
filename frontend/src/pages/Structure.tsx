import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, type Department, type Establishment, type JobPosition } from '../api'
import { Badge, Card, Icon } from '../stitch'

const CATEGORIES = [
  { key: '', label: '—' },
  { key: 'cadre', label: 'Cadre' },
  { key: 'employe', label: 'Employé' },
  { key: 'ouvrier_horaire', label: 'Ouvrier (horaire)' },
]
const CATLABEL: Record<string, string> = { cadre: 'Cadre', employe: 'Employé', ouvrier_horaire: 'Ouvrier (horaire)' }
const champ = 'w-full px-3 py-2 rounded-lg border border-border bg-white text-ink text-body-sm outline-none focus:border-secondary-fixed-dim focus:ring-2 focus:ring-secondary-fixed-dim/30'

export default function Structure() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [etabs, setEtabs] = useState<Establishment[] | null>(null)
  const [depts, setDepts] = useState<Department[] | null>(null)
  const [postes, setPostes] = useState<JobPosition[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [fe, setFe] = useState({ nom: '', adresse: '', num_cnss_etab: '' })
  const [fd, setFd] = useState({ nom: '', centre_de_cout: '' })
  const [fp, setFp] = useState({ intitule: '', categorie: '', classification_conv: '' })

  const reloadE = () => api.establishments(cid).then((r) => setEtabs(r.etablissements)).catch((e) => setError(msg(e)))
  const reloadD = () => api.departments(cid).then((r) => setDepts(r.departements)).catch((e) => setError(msg(e)))
  const reloadP = () => api.positions(cid).then((r) => setPostes(r.postes)).catch((e) => setError(msg(e)))
  const msg = (e: unknown) => (e instanceof ApiError ? e.message : 'Erreur réseau')
  useEffect(() => { reloadE(); reloadD(); reloadP() }, [cid])

  const addE = () => {
    if (!fe.nom.trim()) return
    setBusy('e'); setError(null)
    api.createEstablishment({ company_id: cid, nom: fe.nom.trim(), adresse: fe.adresse || null, num_cnss_etab: fe.num_cnss_etab || null })
      .then(() => { setFe({ nom: '', adresse: '', num_cnss_etab: '' }); return reloadE() })
      .catch((e) => setError(msg(e))).finally(() => setBusy(null))
  }
  const addD = () => {
    if (!fd.nom.trim()) return
    setBusy('d'); setError(null)
    api.createDepartment({ company_id: cid, nom: fd.nom.trim(), centre_de_cout: fd.centre_de_cout || null })
      .then(() => { setFd({ nom: '', centre_de_cout: '' }); return reloadD() })
      .catch((e) => setError(msg(e))).finally(() => setBusy(null))
  }
  const addP = () => {
    if (!fp.intitule.trim()) return
    setBusy('p'); setError(null)
    api.createPosition({ company_id: cid, intitule: fp.intitule.trim(), categorie: fp.categorie || null, classification_conv: fp.classification_conv || null })
      .then(() => { setFp({ intitule: '', categorie: '', classification_conv: '' }); return reloadP() })
      .catch((e) => setError(msg(e))).finally(() => setBusy(null))
  }

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Structure de l'entreprise</h2>
          <Badge tone="neutral" icon="account_tree">Établissements · Départements · Postes</Badge>
        </div>
        <p className="text-body-md text-muted mt-1 max-w-2xl">Organisation de la société : établissements (CNSS), départements (centres de coût) et postes (catégories). Ces éléments structurent les contrats et la paie.</p>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Établissements */}
        <Card className="p-0 overflow-hidden flex flex-col">
          <div className="p-4 border-b border-border flex items-center gap-2"><Icon name="apartment" className="text-primary" /><h3 className="text-subtitle-md font-bold text-ink">Établissements</h3></div>
          <div className="p-4 flex flex-col gap-2 border-b border-border">
            <input className={champ} placeholder="Nom de l'établissement *" value={fe.nom} onChange={(e) => setFe({ ...fe, nom: e.target.value })} />
            <input className={champ} placeholder="Adresse" value={fe.adresse} onChange={(e) => setFe({ ...fe, adresse: e.target.value })} />
            <input className={champ} placeholder="N° CNSS établissement" value={fe.num_cnss_etab} onChange={(e) => setFe({ ...fe, num_cnss_etab: e.target.value })} />
            <button onClick={addE} disabled={!fe.nom.trim() || busy === 'e'} className="inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-primary text-on-primary font-bold text-body-sm rounded-lg hover:bg-primary-container disabled:opacity-50"><Icon name="add" className="text-[16px]" /> Ajouter</button>
          </div>
          <div className="flex-1 divide-y divide-border">
            {etabs == null ? <div className="p-4 text-muted text-body-sm flex items-center gap-2"><span className="spinner" /> …</div>
              : etabs.length === 0 ? <div className="p-6 text-center text-muted text-body-sm">Aucun établissement.</div>
              : etabs.map((x) => (
                <div key={x.id} className="p-3 px-4">
                  <div className="font-bold text-ink text-body-sm">{x.nom}</div>
                  <div className="text-label-md text-muted">{x.adresse || '—'}{x.num_cnss_etab ? ` · CNSS ${x.num_cnss_etab}` : ''}</div>
                </div>
              ))}
          </div>
        </Card>

        {/* Départements */}
        <Card className="p-0 overflow-hidden flex flex-col">
          <div className="p-4 border-b border-border flex items-center gap-2"><Icon name="workspaces" className="text-secondary" /><h3 className="text-subtitle-md font-bold text-ink">Départements</h3></div>
          <div className="p-4 flex flex-col gap-2 border-b border-border">
            <input className={champ} placeholder="Nom du département *" value={fd.nom} onChange={(e) => setFd({ ...fd, nom: e.target.value })} />
            <input className={champ} placeholder="Centre de coût" value={fd.centre_de_cout} onChange={(e) => setFd({ ...fd, centre_de_cout: e.target.value })} />
            <button onClick={addD} disabled={!fd.nom.trim() || busy === 'd'} className="inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-primary text-on-primary font-bold text-body-sm rounded-lg hover:bg-primary-container disabled:opacity-50"><Icon name="add" className="text-[16px]" /> Ajouter</button>
          </div>
          <div className="flex-1 divide-y divide-border">
            {depts == null ? <div className="p-4 text-muted text-body-sm flex items-center gap-2"><span className="spinner" /> …</div>
              : depts.length === 0 ? <div className="p-6 text-center text-muted text-body-sm">Aucun département.</div>
              : depts.map((x) => (
                <div key={x.id} className="p-3 px-4">
                  <div className="font-bold text-ink text-body-sm">{x.nom}</div>
                  <div className="text-label-md text-muted">{x.centre_de_cout ? `Centre de coût : ${x.centre_de_cout}` : '—'}</div>
                </div>
              ))}
          </div>
        </Card>

        {/* Postes */}
        <Card className="p-0 overflow-hidden flex flex-col">
          <div className="p-4 border-b border-border flex items-center gap-2"><Icon name="badge" className="text-primary" /><h3 className="text-subtitle-md font-bold text-ink">Postes</h3></div>
          <div className="p-4 flex flex-col gap-2 border-b border-border">
            <input className={champ} placeholder="Intitulé du poste *" value={fp.intitule} onChange={(e) => setFp({ ...fp, intitule: e.target.value })} />
            <select className={champ} value={fp.categorie} onChange={(e) => setFp({ ...fp, categorie: e.target.value })}>
              {CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.key ? c.label : 'Catégorie —'}</option>)}
            </select>
            <input className={champ} placeholder="Classification conventionnelle" value={fp.classification_conv} onChange={(e) => setFp({ ...fp, classification_conv: e.target.value })} />
            <button onClick={addP} disabled={!fp.intitule.trim() || busy === 'p'} className="inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-primary text-on-primary font-bold text-body-sm rounded-lg hover:bg-primary-container disabled:opacity-50"><Icon name="add" className="text-[16px]" /> Ajouter</button>
          </div>
          <div className="flex-1 divide-y divide-border">
            {postes == null ? <div className="p-4 text-muted text-body-sm flex items-center gap-2"><span className="spinner" /> …</div>
              : postes.length === 0 ? <div className="p-6 text-center text-muted text-body-sm">Aucun poste.</div>
              : postes.map((x) => (
                <div key={x.id} className="p-3 px-4 flex items-center justify-between gap-2">
                  <div>
                    <div className="font-bold text-ink text-body-sm">{x.intitule}</div>
                    <div className="text-label-md text-muted">{x.classification_conv || '—'}</div>
                  </div>
                  {x.categorie && <Badge tone="neutral">{CATLABEL[x.categorie] ?? x.categorie}</Badge>}
                </div>
              ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
