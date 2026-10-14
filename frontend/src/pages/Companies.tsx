import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError, type Company } from '../api'
import { Badge, Button, Card, Icon, PageHeader } from '../stitch'

export default function Companies() {
  const [companies, setCompanies] = useState<Company[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const navigate = useNavigate()

  useEffect(() => {
    api.companies()
      .then((r) => setCompanies(r.companies))
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }, [])

  const filtered = useMemo(() => {
    if (!companies) return null
    const needle = q.trim().toLowerCase()
    if (!needle) return companies
    return companies.filter((c) =>
      [c.raison_sociale, c.nom, c.ifu].some((v) => v?.toLowerCase().includes(needle)),
    )
  }, [companies, q])

  return (
    <>
      <PageHeader
        title="Portefeuille"
        subtitle="Les sociétés de votre périmètre. Ouvrez un dossier pour gérer l’équipe, la paie et les déclarations."
        badge={companies && <Badge tone="neutral">{companies.length} {companies.length > 1 ? 'dossiers' : 'dossier'}</Badge>}
        actions={<Button variant="primary" icon="add_business" onClick={() => navigate('/nouvelle-societe')}>Créer une société</Button>}
      />

      {/* Barre de recherche locale */}
      <div className="relative max-w-md">
        <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-muted text-[18px]" />
        <input
          value={q}
          onChange={(e) => setParams(e.target.value ? { q: e.target.value } : {}, { replace: true })}
          placeholder="Rechercher par nom ou IFU…"
          className="w-full pl-9 pr-4 py-2 text-body-md bg-surface border border-border rounded-xl focus:outline-none focus:border-secondary focus:ring-1 focus:ring-secondary transition-all"
        />
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>
      )}

      {filtered == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement des sociétés…</div>
      ) : filtered.length === 0 ? (
        <Card className="p-10 text-center">
          <Icon name="domain_disabled" className="text-[40px] text-outline-variant" />
          <p className="text-muted mt-2">{q ? 'Aucune société ne correspond à votre recherche.' : 'Aucune société dans votre périmètre.'}</p>
          {!q && <div className="mt-3 flex justify-center"><Button variant="primary" icon="add_business" onClick={() => navigate('/nouvelle-societe')}>Créer une société</Button></div>}
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((c) => (
            <Link
              key={c.id}
              to={`/c/${c.id}`}
              className="group bg-surface rounded-2xl border border-border shadow-sm p-5 flex items-start justify-between gap-3 hover:border-secondary transition-colors"
            >
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-11 h-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-extrabold shrink-0">
                  {(c.raison_sociale ?? c.nom ?? 'S').slice(0, 2).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <h3 className="text-subtitle-md font-bold text-ink truncate">{c.raison_sociale ?? c.nom ?? 'Société'}</h3>
                  <span className="text-label-md text-muted">{c.ifu ? `IFU ${c.ifu}` : 'IFU non renseigné'}</span>
                </div>
              </div>
              <Icon name="arrow_forward" className="text-outline-variant group-hover:text-secondary transition-colors" />
            </Link>
          ))}
        </div>
      )}
    </>
  )
}
