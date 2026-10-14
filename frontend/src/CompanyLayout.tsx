import { useEffect, useState } from 'react'
import { NavLink, Outlet, useParams } from 'react-router-dom'
import { api, type Company } from './api'
import { Icon } from './stitch'

const TABS = [
  { to: 'salaries', label: 'Équipe', icon: 'group' },
  { to: 'paie', label: 'Paie', icon: 'payments' },
  { to: 'declarations', label: 'Déclarations', icon: 'description' },
  { to: 'comptabilite', label: 'Comptabilité', icon: 'account_balance' },
  { to: 'reporting', label: 'Reporting', icon: 'bar_chart' },
]

export default function CompanyLayout() {
  const { companyId } = useParams()
  const base = `/c/${companyId}`
  const [company, setCompany] = useState<Company | null>(null)

  useEffect(() => {
    api.companies()
      .then((r) => setCompany(r.companies.find((c) => c.id === companyId) ?? null))
      .catch(() => setCompany(null))
  }, [companyId])

  const name = company?.raison_sociale ?? company?.nom ?? 'Société'

  return (
    <div className="flex flex-col gap-5">
      {/* En-tête société */}
      <div className="flex items-center gap-3">
        <NavLink to="/portefeuille" className="p-2 rounded-lg text-muted hover:text-ink hover:bg-surface-container transition-colors" title="Retour au portefeuille">
          <Icon name="arrow_back" className="text-[20px]" />
        </NavLink>
        <div className="w-11 h-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-extrabold">
          {name.slice(0, 2).toUpperCase()}
        </div>
        <div>
          <h1 className="text-headline-md font-headline-md text-ink">{name}</h1>
          {company?.ifu && <span className="text-label-md text-muted">IFU {company.ifu}</span>}
        </div>
      </div>

      {/* Onglets */}
      <nav className="flex items-center gap-1 border-b border-border overflow-x-auto">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={`${base}/${t.to}`}
            className={({ isActive }) =>
              `flex items-center gap-1.5 px-4 py-2.5 text-label-lg font-bold border-b-2 -mb-px transition-colors whitespace-nowrap ${
                isActive
                  ? 'border-secondary text-secondary'
                  : 'border-transparent text-muted hover:text-ink'
              }`
            }
          >
            <Icon name={t.icon} className="text-[18px]" />
            {t.label}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </div>
  )
}
