import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, type Company } from '../api'
import { Spinner } from '../ui'

export default function Companies() {
  const [companies, setCompanies] = useState<Company[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.companies()
      .then((r) => setCompanies(r.companies))
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }, [])

  if (error) return <div className="error">{error}</div>
  if (!companies) return <div className="row"><Spinner /> <span className="muted">Chargement des sociétés…</span></div>

  return (
    <div>
      <h2>Sociétés <span className="badge">{companies.length}</span></h2>
      {companies.length === 0 ? (
        <p className="muted">Aucune société dans votre périmètre.</p>
      ) : (
        <div className="list">
          {companies.map((c) => (
            <Link key={c.id} to={`/c/${c.id}`} className="card list-item" style={{ color: 'inherit' }}>
              <div>
                <h3>{c.raison_sociale ?? c.nom ?? 'Société'}</h3>
                {c.ifu && <span className="muted">IFU {c.ifu}</span>}
              </div>
              <span className="muted" aria-hidden="true">→</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
