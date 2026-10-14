import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, type Company } from '../api'
import { Badge, Card, Icon, PageHeader, StatCard } from '../stitch'

const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

export default function Dashboard() {
  const [companies, setCompanies] = useState<Company[] | null>(null)
  const [headcount, setHeadcount] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api.companies()
      .then(async (r) => {
        if (!alive) return
        setCompanies(r.companies)
        // Effectif total réel = somme des salariés sur le périmètre (requêtes en parallèle).
        try {
          const counts = await Promise.all(
            r.companies.map((c) => api.employees(c.id).then((e) => e.employes.length).catch(() => 0)),
          )
          if (alive) setHeadcount(counts.reduce((a, b) => a + b, 0))
        } catch { /* effectif indisponible */ }
      })
      .catch((e) => alive && setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
    return () => { alive = false }
  }, [])

  const now = new Date()
  const periodeLabel = `${MOIS[now.getMonth()]} ${now.getFullYear()}`
  const nbSoc = companies?.length ?? null

  return (
    <>
      <PageHeader
        title="Tableau de bord"
        subtitle="Supervision des cycles de paie, conformité fiscale DGI et déclarations sociales CNSS (Bénin)."
        badge={<Badge tone="secondary" icon="radio_button_checked">Période active</Badge>}
        actions={
          <div className="flex items-center gap-2 bg-surface px-3 py-1.5 rounded-xl border border-border shadow-sm">
            <Icon name="calendar_today" className="text-muted text-[18px]" />
            <span className="text-label-lg font-bold text-ink capitalize">{periodeLabel}</span>
          </div>
        }
      />

      {error && (
        <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">
          {error}
        </div>
      )}

      {/* KPI réels */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <StatCard
          label="Sociétés gérées"
          value={nbSoc == null ? '—' : nbSoc}
          icon="domain"
          footLeft="Dans votre périmètre"
          footRight={
            <Link to="/portefeuille" className="text-secondary font-bold flex items-center gap-0.5 hover:underline">
              Voir <Icon name="arrow_forward" className="text-[14px]" />
            </Link>
          }
        />
        <StatCard
          label="Salariés actifs"
          value={headcount == null ? '—' : headcount}
          icon="badge"
          footLeft={headcount == null ? 'Calcul en cours…' : 'Sur l’ensemble du portefeuille'}
        />
        <StatCard
          label="Masse salariale"
          value="—"
          unit="FCFA"
          icon="payments"
          footLeft="Disponible après un cycle calculé"
        />
      </section>

      {/* Prochaine action + échéances */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-8 bg-primary-container text-surface-container-lowest rounded-2xl p-6 border border-border/10 shadow-sm flex flex-col justify-between">
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded-lg bg-surface-container-lowest/10 text-secondary-fixed text-label-md font-bold tracking-wide uppercase">
                Action prioritaire
              </span>
              <span className="text-label-md text-on-primary-container capitalize">{periodeLabel}</span>
            </div>
            <div>
              <h2 className="text-headline-md text-surface-container-lowest">Préparez votre cycle de paie</h2>
              <p className="text-body-md text-on-primary-container mt-1 max-w-2xl">
                {nbSoc === 0
                  ? "Aucune société n'est encore enregistrée. Commencez par créer votre première société pour lancer un cycle."
                  : 'Ouvrez une société de votre portefeuille pour saisir les variables, calculer les bulletins et finaliser les déclarations.'}
              </p>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-on-primary-container/20">
            <span className="flex items-center gap-1.5 text-label-md text-on-primary-container">
              <Icon name="done_all" className="text-secondary-fixed text-[16px]" />
              Barème ITS/VPS &amp; taux CNSS intégrés
            </span>
            <Link
              to={nbSoc === 0 ? '/nouvelle-societe' : '/portefeuille'}
              className="px-6 py-3 bg-secondary-fixed hover:bg-secondary-fixed-dim text-ink font-extrabold text-subtitle-md rounded-xl transition-all duration-150 active:scale-95 shadow-md flex items-center gap-2"
            >
              <span>{nbSoc === 0 ? 'Créer une société' : 'Aller au portefeuille'}</span>
              <Icon name="arrow_forward" className="text-[18px]" />
            </Link>
          </div>
        </div>

        <Card className="lg:col-span-4 p-6 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="text-subtitle-lg font-subtitle-lg text-ink">Échéances déclaratives</h3>
            <Badge tone="secondary">Bénin</Badge>
          </div>
          <p className="text-body-md text-muted">Obligations mensuelles récurrentes à anticiper pour chaque société.</p>
          <div className="flex flex-col gap-3">
            <div className="p-3 rounded-xl bg-surface-container-low border border-border flex items-start gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-warning/10 text-warning flex items-center justify-center shrink-0 mt-0.5">
                <Icon name="gavel" className="text-[18px]" />
              </div>
              <div className="flex flex-col">
                <div className="text-label-lg font-bold text-ink">Déclaration ITS / VPS</div>
                <span className="text-label-md text-muted">Impôt sur Traitements &amp; Salaires — DGI</span>
              </div>
            </div>
            <div className="p-3 rounded-xl bg-surface-container-low border border-border flex items-start gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5">
                <Icon name="verified" className="text-[18px]" />
              </div>
              <div className="flex flex-col">
                <div className="text-label-lg font-bold text-ink">Cotisations CNSS</div>
                <span className="text-label-md text-muted">Déclaration sociale mensuelle</span>
              </div>
            </div>
          </div>
          <Link to="/conformite" className="mt-1 pt-3 border-t border-border flex items-center gap-2 text-label-md text-secondary font-semibold hover:underline">
            <Icon name="verified_user" className="text-[18px]" />
            Voir le calendrier de conformité
          </Link>
        </Card>
      </section>

      {/* Aperçu portefeuille */}
      <Card className="overflow-hidden flex flex-col">
        <div className="p-4 px-6 border-b border-border flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h3 className="text-subtitle-lg font-subtitle-lg text-ink">Portefeuille</h3>
            {nbSoc != null && (
              <span className="px-2 py-0.5 text-label-md font-bold bg-surface-container text-muted rounded-full">
                {nbSoc} {nbSoc > 1 ? 'dossiers' : 'dossier'}
              </span>
            )}
          </div>
          <Link to="/portefeuille" className="text-label-md font-bold text-secondary hover:underline flex items-center gap-1">
            Tout voir <Icon name="arrow_forward" className="text-[14px]" />
          </Link>
        </div>
        {companies == null ? (
          <div className="p-6 flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
        ) : companies.length === 0 ? (
          <div className="p-8 text-center text-muted">Aucune société dans votre périmètre.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-border text-label-lg font-bold text-muted">
                  <th className="py-3 px-6">Société</th>
                  <th className="py-3 px-4">IFU</th>
                  <th className="py-3 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-body-md text-ink">
                {companies.slice(0, 6).map((c) => (
                  <tr key={c.id} className="hover:bg-primary-fixed/20 transition-colors">
                    <td className="py-3.5 px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">
                          {(c.raison_sociale ?? c.nom ?? 'S').slice(0, 2).toUpperCase()}
                        </div>
                        <span className="font-bold text-ink">{c.raison_sociale ?? c.nom ?? 'Société'}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-label-md text-muted tabular-nums">{c.ifu ?? '—'}</td>
                    <td className="py-3.5 px-6 text-right">
                      <Link to={`/c/${c.id}`} className="text-secondary font-bold hover:underline inline-flex items-center gap-1">
                        Ouvrir <Icon name="arrow_forward" className="text-[14px]" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
