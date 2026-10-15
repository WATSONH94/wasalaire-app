import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, type AdminOverview } from '../../api'
import { Card, Icon, PageHeader, StatCard } from '../../stitch'

export default function AdminDashboard() {
  const [ov, setOv] = useState<AdminOverview | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.adminOverview().then(setOv).catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }, [])

  return (
    <>
      <PageHeader title="Tableau de bord plateforme" subtitle="Vue d’ensemble de l’exploitation WaSalaire (données réelles)." />

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {ov == null && !error ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : ov && (
        <>
          <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
            <StatCard label="Organisations clientes" value={ov.organizations} icon="domain" footLeft="Cabinets & entreprises" footRight={<Link to="/organizations" className="text-secondary font-bold hover:underline">Gérer</Link>} />
            <StatCard label="Sociétés gérées" value={ov.companies} icon="apartment" footLeft={`${ov.establishments} établissements`} />
            <StatCard label="Utilisateurs actifs" value={ov.users_active} icon="group" footLeft={`${ov.internal_users} internes`} />
            <StatCard label="Salariés administrés" value={ov.employees} icon="badge" />
          </section>
          <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
            <StatCard label="Bulletins produits" value={ov.payslips} icon="receipt_long" />
            <StatCard label="Cycles de paie" value={ov.runs_total} icon="payments" />
            <StatCard label="Abonnements actifs" value={ov.subscriptions_active} icon="card_membership" footLeft={`${ov.subscriptions_total} au total`} footRight={<Link to="/subscriptions" className="text-secondary font-bold hover:underline">Voir</Link>} />
            <StatCard label="Comptes internes" value={ov.internal_users} icon="shield_person" footRight={<Link to="/internal-users" className="text-secondary font-bold hover:underline">Gérer</Link>} />
          </section>

          <Card className="p-6 flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-secondary/10 text-secondary flex items-center justify-center shrink-0"><Icon name="verified_user" /></div>
            <div>
              <h3 className="text-subtitle-md font-bold text-ink">Santé & conformité</h3>
              <p className="text-body-md text-muted mt-1">
                Les indicateurs ci-dessus proviennent directement des données applicatives (aucune donnée simulée).
                La supervision technique détaillée (API, jobs, sauvegardes) est dans le module Supervision.
              </p>
            </div>
          </Card>
        </>
      )}
    </>
  )
}
