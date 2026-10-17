import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Declaration, type Run } from '../api'
import { Badge, Card, Icon } from '../stitch'

const MOIS = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

function Ligne({ label, value, strong }: { label: string; value: number; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">
      <span className="text-body-md text-muted">{label}</span>
      <span className={`tabular-nums ${strong ? 'font-extrabold text-ink' : 'font-semibold text-ink'}`}>{fcfa(value)}</span>
    </div>
  )
}

export default function Declarations() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [sel, setSel] = useState<string | null>(null)
  const [decl, setDecl] = useState<Declaration | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingDecl, setLoadingDecl] = useState(false)

  useEffect(() => {
    api.companyRuns(cid)
      .then((r) => {
        // Seuls les cycles ACTIFS sont déclarables : un run superseded (recalculé)
        // ne doit pas apparaître, sinon le non-expert risque de déclarer de faux montants.
        const actifs = r.runs.filter((x) => x.actif !== false)
        setRuns(actifs)
        const first = actifs.find((x) => x.statut === 'cloturee') ?? actifs[0]
        if (first) setSel(first.run_id)
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }, [cid])

  useEffect(() => {
    if (!sel) return
    setLoadingDecl(true); setDecl(null)
    api.declarationFull(sel)
      .then(setDecl)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
      .finally(() => setLoadingDecl(false))
  }, [sel])

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h2 className="text-subtitle-lg font-subtitle-lg text-ink">Déclarations DGI &amp; CNSS</h2>
        <Badge tone="secondary" icon="verified_user">Bénin</Badge>
      </div>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {runs == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : runs.length === 0 ? (
        <Card className="p-10 text-center">
          <Icon name="receipt_long" className="text-[40px] text-outline-variant" />
          <p className="text-muted mt-2">Aucun cycle calculé. Les déclarations sont générées après le calcul d’une paie.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Liste des cycles */}
          <Card className="p-3 lg:col-span-1 h-fit">
            <div className="text-label-md font-bold text-muted uppercase px-2 py-1">Cycles</div>
            <div className="flex flex-col gap-1">
              {runs.map((r) => (
                <button
                  key={r.run_id}
                  onClick={() => setSel(r.run_id)}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-colors ${
                    sel === r.run_id ? 'bg-secondary/10 text-secondary' : 'hover:bg-surface-container-low text-ink'
                  }`}
                >
                  <span className="font-bold capitalize">{MOIS[r.mois]} {r.annee}</span>
                  <Badge tone={r.statut === 'cloturee' ? 'success' : 'neutral'}>{r.statut === 'cloturee' ? 'Clôturé' : r.statut}</Badge>
                </button>
              ))}
            </div>
          </Card>

          {/* Détail déclaration */}
          <div className="lg:col-span-2 flex flex-col gap-5">
            {loadingDecl ? (
              <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement de la déclaration…</div>
            ) : decl ? (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <Card className="p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-9 h-9 rounded-xl bg-warning/10 text-warning flex items-center justify-center"><Icon name="gavel" /></div>
                      <div>
                        <h3 className="text-subtitle-md font-bold text-ink">ITS / VPS — DGI</h3>
                        <span className="text-label-md text-muted">Échéance : le 10 du mois suivant</span>
                      </div>
                    </div>
                    <Ligne label="Base ITS" value={decl.its_vps.base_its_total} />
                    <Ligne label="ITS total" value={decl.its_vps.its_total} />
                    <Ligne label="VPS total" value={decl.its_vps.vps_total} strong />
                  </Card>
                  <Card className="p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-9 h-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center"><Icon name="verified" /></div>
                      <div>
                        <h3 className="text-subtitle-md font-bold text-ink">CNSS</h3>
                        <span className="text-label-md text-muted">Cotisations sociales</span>
                      </div>
                    </div>
                    <Ligne label="Assiette CNSS" value={decl.cnss.assiette} />
                    <Ligne label="Part salariale" value={decl.cnss.salariale} />
                    <Ligne label="Part patronale" value={decl.cnss.patronale} strong />
                  </Card>
                </div>
                <Card className="p-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Icon name="groups" className="text-muted" />
                      <span className="text-label-md text-muted">{decl.bulletins} bulletin{decl.bulletins > 1 ? 's' : ''} · AMO salariale {fcfa(decl.amo.salariale)} · patronale {fcfa(decl.amo.patronale)}</span>
                    </div>
                    <div className="text-right">
                      <div className="text-label-md text-muted">Net total</div>
                      <div className="text-subtitle-lg font-extrabold text-secondary tabular-nums">{fcfa(decl.net_total)}</div>
                    </div>
                  </div>
                  <p className="text-label-md text-muted mt-3 flex items-start gap-1.5">
                    <Icon name="info" className="text-[16px] mt-0.5" />
                    Montants calculés par le moteur. Le dépôt officiel DGI/CNSS reste une démarche externe.
                  </p>
                </Card>
              </>
            ) : (
              <Card className="p-8 text-center text-muted">Sélectionnez un cycle pour voir sa déclaration.</Card>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
