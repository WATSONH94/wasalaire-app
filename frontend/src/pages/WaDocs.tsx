import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, type DocListItem, type DocTemplate, type Employee, type GeneratedDoc } from '../api'
import { Badge, Card, Icon } from '../stitch'

const CATEGORIES = [
  { key: 'courrier', label: 'Courrier' },
  { key: 'embauche', label: 'Embauche' },
  { key: 'vie_salarie', label: 'Vie du salarié' },
  { key: 'paie', label: 'Paie' },
  { key: 'depart', label: 'Départ' },
  { key: 'declarations', label: 'Déclarations' },
]
const CHAMPS = ['{{Entreprise.raison_sociale}}', '{{Entreprise.ifu}}', '{{Salarié.nom}}', '{{Contrat.poste}}', '{{Contrat.type}}', '{{Contrat.date_debut}}', '{{Contrat.salaire | money}}']

export default function WaDocs() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [emps, setEmps] = useState<Employee[] | null>(null)
  const [templates, setTemplates] = useState<DocTemplate[]>([])
  const [selEmp, setSelEmp] = useState('')
  const [selTpl, setSelTpl] = useState('')   // '' = contrat de travail intégré ; sinon id de modèle
  const [doc, setDoc] = useState<GeneratedDoc | null>(null)
  const [list, setList] = useState<DocListItem[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Création de modèle
  const [showNew, setShowNew] = useState(false)
  const [nt, setNt] = useState({ name: '', category: 'courrier', contenu: '' })

  const msg = (e: unknown) => (e instanceof ApiError ? e.message : 'Erreur réseau')
  const reloadList = () => api.documentsList(cid).then((r) => setList(r.documents)).catch(() => setList([]))
  const reloadTpl = () => api.documentTemplates(cid).then((r) => setTemplates(r.templates)).catch(() => setTemplates([]))
  useEffect(() => { api.employees(cid).then((r) => setEmps(r.employes)).catch(() => setEmps([])); reloadList(); reloadTpl() }, [cid])

  const tplName = selTpl ? (templates.find((t) => t.id === selTpl)?.name ?? 'Document') : 'Contrat de travail'

  const generer = () => {
    if (!selEmp) return
    setBusy(true); setError(null); setDoc(null)
    api.generateDocument(cid, selEmp, tplName, selTpl || undefined)
      .then((d) => { setDoc(d); return reloadList() })
      .catch((e) => setError(msg(e)))
      .finally(() => setBusy(false))
  }

  const creerModele = () => {
    if (!nt.name.trim() || !nt.contenu.trim()) return
    setBusy(true); setError(null)
    api.createDocumentTemplate({ company_id: cid, name: nt.name.trim(), category: nt.category, contenu: nt.contenu })
      .then((r) => { setNt({ name: '', category: 'courrier', contenu: '' }); setShowNew(false); return reloadTpl().then(() => setSelTpl(r.template_id)) })
      .catch((e) => setError(msg(e)))
      .finally(() => setBusy(false))
  }

  const champ = 'w-full px-3 py-2.5 rounded-xl border border-border bg-white text-ink outline-none focus:border-secondary-fixed-dim focus:ring-2 focus:ring-secondary-fixed-dim/30'

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6 print:hidden">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">WaDocs — Documents &amp; modèles</h2>
          <Badge tone="neutral" icon="description">Fusion de champs</Badge>
        </div>
        <p className="text-body-md text-muted mt-1 max-w-2xl">Génération de documents à partir de modèles et des données réelles du dossier. Créez vos propres modèles avec des champs de fusion <code className="text-ink">{'{{…}}'}</code>. Chaque document est horodaté et empreinté (hash).</p>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold print:hidden">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Génération + modèles */}
        <Card className="p-5 lg:col-span-1 h-fit flex flex-col gap-3 print:hidden">
          <div className="flex items-center gap-2"><Icon name="note_add" className="text-secondary" /><h3 className="text-subtitle-md font-bold text-ink">Générer un document</h3></div>
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-label-md font-semibold text-ink">Modèle</span>
              <button onClick={() => setShowNew((v) => !v)} className="text-label-md font-bold text-secondary hover:underline inline-flex items-center gap-1"><Icon name={showNew ? 'close' : 'add'} className="text-[16px]" />{showNew ? 'Fermer' : 'Nouveau modèle'}</button>
            </div>
            <select className={champ} value={selTpl} onChange={(e) => setSelTpl(e.target.value)}>
              <option value="">Contrat de travail (intégré)</option>
              {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>

          {showNew && (
            <div className="p-3 rounded-xl border border-border bg-surface-container-low/50 flex flex-col gap-2">
              <input className={champ} placeholder="Nom du modèle *" value={nt.name} onChange={(e) => setNt({ ...nt, name: e.target.value })} />
              <select className={champ} value={nt.category} onChange={(e) => setNt({ ...nt, category: e.target.value })}>
                {CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
              <textarea className={`${champ} min-h-[120px] font-mono text-body-sm`} placeholder="Contenu du modèle avec des champs {{…}}" value={nt.contenu} onChange={(e) => setNt({ ...nt, contenu: e.target.value })} />
              <div className="text-[11px] text-muted">Champs disponibles : {CHAMPS.map((c) => <button key={c} type="button" onClick={() => setNt((s) => ({ ...s, contenu: s.contenu + c }))} className="inline-block m-0.5 px-1.5 py-0.5 rounded bg-surface-container font-mono text-ink hover:bg-surface-container-high">{c}</button>)}</div>
              <button onClick={creerModele} disabled={!nt.name.trim() || !nt.contenu.trim() || busy} className="inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-secondary text-white font-bold text-body-sm rounded-lg hover:opacity-90 disabled:opacity-50"><Icon name="save" className="text-[16px]" /> Enregistrer le modèle</button>
            </div>
          )}

          <div><span className="block text-label-md font-semibold text-ink mb-1">Salarié</span>
            <select className={champ} value={selEmp} onChange={(e) => setSelEmp(e.target.value)}>
              <option value="">— Sélectionner —</option>
              {(emps ?? []).map((e) => <option key={e.id} value={e.id}>{e.nom} ({e.matricule})</option>)}
            </select>
          </div>
          <button onClick={generer} disabled={!selEmp || busy} className="mt-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container shadow-sm disabled:opacity-50">
            <Icon name="auto_awesome" className="text-[18px]" /> {busy ? 'Génération…' : 'Générer le document'}
          </button>

          <div className="mt-2 pt-3 border-t border-border">
            <div className="text-label-md font-bold text-muted uppercase mb-2">Documents générés</div>
            {list == null ? <div className="text-muted text-body-sm flex items-center gap-2"><span className="spinner" /> …</div>
              : list.length === 0 ? <div className="text-muted text-body-sm">Aucun document.</div>
              : <div className="flex flex-col gap-1 max-h-48 overflow-y-auto">
                  {list.map((d, i) => (
                    <div key={i} className="flex items-center justify-between py-1.5 text-body-sm">
                      <span className="text-ink font-semibold truncate">{d.titre}</span>
                      <span className="text-label-md text-muted shrink-0 ml-2">{String(d.date).slice(0, 10)}</span>
                    </div>
                  ))}
                </div>}
          </div>
        </Card>

        {/* Aperçu */}
        <div className="lg:col-span-2">
          {!doc ? (
            <Card className="p-10 text-center text-muted"><Icon name="draft" className="text-[40px] text-outline-variant" /><p className="mt-2">Choisissez un modèle et un salarié, puis générez le document pour l'aperçu.</p></Card>
          ) : (
            <Card className="p-0 overflow-hidden">
              <div className="p-5 border-b border-border flex items-center justify-between gap-2 print:hidden">
                <div><h3 className="text-subtitle-md font-bold text-ink">{doc.titre}</h3><span className="text-label-md text-muted font-mono">Empreinte : {doc.hash.slice(0, 16)}…</span></div>
                <button onClick={() => window.print()} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-secondary-fixed text-ink font-bold text-label-md rounded-lg hover:bg-secondary-fixed-dim"><Icon name="print" className="text-[18px]" /> Imprimer</button>
              </div>
              <div className="p-8">
                <pre className="whitespace-pre-wrap text-body-md text-ink leading-relaxed" style={{ fontFamily: 'inherit' }}>{doc.contenu}</pre>
              </div>
              <p className="p-4 text-label-md text-muted flex items-start gap-1.5 print:hidden"><Icon name="info" className="text-[16px] mt-0.5" />Document fusionné depuis les données réelles. Un champ manquant apparaît « [champ ?] ». Export PDF/signature électronique = étape ultérieure.</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
