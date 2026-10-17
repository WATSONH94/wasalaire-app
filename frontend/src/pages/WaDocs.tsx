import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, type DocListItem, type Employee, type GeneratedDoc } from '../api'
import { Badge, Card, Icon } from '../stitch'

export default function WaDocs() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [emps, setEmps] = useState<Employee[] | null>(null)
  const [selEmp, setSelEmp] = useState('')
  const [titre, setTitre] = useState('Contrat de travail')
  const [doc, setDoc] = useState<GeneratedDoc | null>(null)
  const [list, setList] = useState<DocListItem[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const msg = (e: unknown) => (e instanceof ApiError ? e.message : 'Erreur réseau')
  const reloadList = () => api.documentsList(cid).then((r) => setList(r.documents)).catch(() => setList([]))
  useEffect(() => { api.employees(cid).then((r) => setEmps(r.employes)).catch(() => setEmps([])); reloadList() }, [cid])

  const generer = () => {
    if (!selEmp) return
    setBusy(true); setError(null); setDoc(null)
    api.generateDocument(cid, selEmp, titre || 'Contrat de travail')
      .then((d) => { setDoc(d); return reloadList() })
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
        <p className="text-body-md text-muted mt-1 max-w-2xl">Génération de documents à partir de modèles et des données réelles du dossier (contrat de travail). Chaque document est horodaté et empreinté (hash).</p>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold print:hidden">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Génération */}
        <Card className="p-5 lg:col-span-1 h-fit flex flex-col gap-3 print:hidden">
          <div className="flex items-center gap-2"><Icon name="note_add" className="text-secondary" /><h3 className="text-subtitle-md font-bold text-ink">Générer un document</h3></div>
          <div><span className="block text-label-md font-semibold text-ink mb-1">Modèle</span>
            <select className={champ} value={titre} onChange={(e) => setTitre(e.target.value)}>
              <option value="Contrat de travail">Contrat de travail</option>
            </select>
            <span className="block text-[11px] text-muted mt-1">D'autres modèles (attestations, avenants) via les pages dédiées ; l'éditeur de modèles arrive.</span>
          </div>
          <div><span className="block text-label-md font-semibold text-ink mb-1">Salarié</span>
            <select className={champ} value={selEmp} onChange={(e) => setSelEmp(e.target.value)}>
              <option value="">— Sélectionner —</option>
              {(emps ?? []).map((e) => <option key={e.id} value={e.id}>{e.nom} ({e.matricule})</option>)}
            </select>
          </div>
          <button onClick={generer} disabled={!selEmp || busy} className="mt-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container shadow-sm disabled:opacity-50">
            <Icon name="auto_awesome" className="text-[18px]" /> {busy ? 'Génération…' : 'Générer le document'}
          </button>

          {/* Historique */}
          <div className="mt-2 pt-3 border-t border-border">
            <div className="text-label-md font-bold text-muted uppercase mb-2">Documents générés</div>
            {list == null ? <div className="text-muted text-body-sm flex items-center gap-2"><span className="spinner" /> …</div>
              : list.length === 0 ? <div className="text-muted text-body-sm">Aucun document.</div>
              : <div className="flex flex-col gap-1 max-h-60 overflow-y-auto">
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
            <Card className="p-10 text-center text-muted"><Icon name="draft" className="text-[40px] text-outline-variant" /><p className="mt-2">Sélectionnez un salarié et générez le document pour l'aperçu.</p></Card>
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
