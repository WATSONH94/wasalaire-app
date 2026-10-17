import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './auth'
import { api, type Company } from './api'
import { Icon } from './stitch'

// Navigation console (markup Stitch exact). Items métier scopés à la société courante.
type NavItem = { label: string; icon: string; to: (c?: string) => string; scoped?: boolean }
const NAV: NavItem[] = [
  { label: 'Accueil', icon: 'dashboard', to: () => '/' },
  { label: 'Portefeuille', icon: 'folder_shared', to: () => '/portefeuille' },
  { label: 'Équipe', icon: 'group', to: (c) => (c ? `/c/${c}/salaries` : '/portefeuille'), scoped: true },
  { label: 'Congés', icon: 'beach_access', to: (c) => (c ? `/c/${c}/conges` : '/portefeuille'), scoped: true },
  { label: 'Paie', icon: 'payments', to: (c) => (c ? `/c/${c}/paie` : '/portefeuille'), scoped: true },
  { label: 'Déclarations', icon: 'description', to: (c) => (c ? `/c/${c}/declarations` : '/portefeuille'), scoped: true },
  { label: 'Comptabilité', icon: 'account_balance', to: (c) => (c ? `/c/${c}/comptabilite` : '/portefeuille'), scoped: true },
  { label: 'Documents', icon: 'folder', to: (c) => (c ? `/c/${c}/documents` : '/portefeuille'), scoped: true },
  { label: 'Rupture / STC', icon: 'person_remove', to: (c) => (c ? `/c/${c}/solde-tout-compte` : '/portefeuille'), scoped: true },
  { label: 'Conformité', icon: 'verified_user', to: () => '/conformite' },
  { label: 'Reporting', icon: 'bar_chart', to: (c) => (c ? `/c/${c}/reporting` : '/portefeuille'), scoped: true },
  { label: 'Paramètres', icon: 'settings', to: () => '/parametres' },
]
const MOIS = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

function currentCompanyId(pathname: string): string | undefined {
  const m = pathname.match(/\/c\/([^/]+)/)
  return m ? m[1] : undefined
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { session, logout } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const companyId = currentCompanyId(pathname)
  const isInternal = !!session?.platform_role && session.platform_role !== 'none'
  const roleLabel = session?.roles?.length ? session.roles.join(' · ') : 'Gestionnaire de paie'

  return (
    <aside className="fixed top-0 left-0 h-screen w-60 z-40 bg-primary-container border-r border-border shadow-sm flex flex-col justify-between p-space-md">
      <div className="flex flex-col gap-space-lg">
        {/* Marque */}
        <div className="flex items-center gap-3 px-space-sm pt-space-xs">
          <div className="w-10 h-10 rounded-xl bg-secondary-fixed flex items-center justify-center shadow-sm">
            <span className="text-primary font-extrabold text-subtitle-lg tracking-tight">W</span>
          </div>
          <div className="flex flex-col">
            <span className="text-headline-md font-headline-md font-extrabold text-surface-container-lowest tracking-tight leading-none">WaSalaire</span>
            <span className="text-label-md font-label-md text-on-primary-container tracking-wide mt-1">Console Bénin</span>
          </div>
        </div>
        {/* CTA Nouveau cycle */}
        <button
          onClick={() => { navigate(companyId ? `/c/${companyId}/paie` : '/portefeuille'); onNavigate?.() }}
          className="w-full flex items-center justify-center gap-2 bg-secondary text-surface-container-lowest py-2.5 px-3 rounded-xl font-subtitle-md text-body-md hover:opacity-90 transition-all duration-150 active:scale-95 shadow-sm"
        >
          <Icon name="add_circle" className="text-[18px]" />
          <span>Nouveau cycle</span>
        </button>
        {/* Navigation */}
        <nav className="flex flex-col gap-1">
          {NAV.map((item) => {
            const to = item.to(companyId)
            const scopedActive = !!item.scoped && !!companyId && to === pathname
            return (
              <NavLink
                key={item.label}
                to={to}
                end={item.to() === '/'}
                onClick={onNavigate}
                className={({ isActive }) =>
                  (isActive || scopedActive)
                    ? 'flex items-center gap-space-md px-space-md py-space-sm bg-secondary text-surface-container-lowest rounded-xl font-bold transition-all duration-150 active:scale-95'
                    : 'flex items-center gap-space-md px-space-md py-space-sm text-on-primary-container hover:text-surface-container-lowest hover:bg-primary rounded-xl font-medium transition-colors duration-150 active:scale-95'
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon name={item.icon} className="text-[20px]" fill={isActive || scopedActive} />
                    <span className="text-label-lg font-label-lg">{item.label}</span>
                  </>
                )}
              </NavLink>
            )
          })}
          {isInternal && (
            <a href="/?surface=admin" className="flex items-center gap-space-md px-space-md py-space-sm text-warning hover:bg-primary rounded-xl font-bold transition-colors duration-150 mt-1">
              <Icon name="admin_panel_settings" className="text-[20px]" />
              <span className="text-label-lg font-label-lg">Admin WaSalaire</span>
            </a>
          )}
        </nav>
      </div>
      {/* Bas : conformité + support + compte */}
      <div className="flex flex-col gap-3 pt-3 border-t border-border/20">
        <div className="bg-primary/50 rounded-xl p-2.5 border border-on-primary-container/20 flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-secondary-fixed tracking-wider uppercase">Conformité</span>
            <span className="inline-block w-2 h-2 rounded-full bg-success"></span>
          </div>
          <div className="text-[11px] font-semibold text-surface-container-lowest leading-tight">Bénin Fiscal DGI &amp; CNSS</div>
          <div className="text-[10px] text-on-primary-container">Barème ITS/VPS synchronisé</div>
        </div>
        <div className="flex items-center justify-between px-1">
          <NavLink to="/parametres" onClick={onNavigate} className="flex items-center gap-2 text-on-primary-container hover:text-surface-container-lowest text-label-md transition-colors duration-150">
            <Icon name="help" className="text-[18px]" />
            <span>Aide &amp; Support</span>
          </NavLink>
          <button onClick={logout} className="text-on-primary-container hover:text-surface-container-lowest transition-colors p-1" title="Déconnexion">
            <Icon name="logout" className="text-[18px]" />
          </button>
        </div>
        <NavLink to="/mon-compte" onClick={onNavigate} className="flex items-center gap-2.5 px-1 py-1 rounded-lg bg-primary/30 hover:bg-primary/50 transition-colors">
          <div className="w-7 h-7 rounded-full bg-surface-container-lowest/10 flex items-center justify-center text-surface-container-lowest text-xs font-bold">
            {(session?.email ?? 'WS').slice(0, 2).toUpperCase()}
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-label-md font-label-md text-surface-container-lowest truncate">{session?.email ?? 'Mon compte'}</span>
            <span className="text-[10px] text-on-primary-container truncate">{roleLabel}</span>
          </div>
        </NavLink>
      </div>
    </aside>
  )
}

function Topbar({ onBurger }: { onBurger: () => void }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const companyId = currentCompanyId(pathname)
  const [q, setQ] = useState('')
  const [company, setCompany] = useState<Company | null>(null)
  const now = new Date()
  const cycle = `${MOIS[now.getMonth() + 1]} ${now.getFullYear()}`

  useEffect(() => {
    if (!companyId) { setCompany(null); return }
    api.companies().then((r) => setCompany(r.companies.find((c) => c.id === companyId) ?? null)).catch(() => setCompany(null))
  }, [companyId])

  const submit = (e: React.FormEvent) => { e.preventDefault(); navigate('/portefeuille' + (q ? `?q=${encodeURIComponent(q)}` : '')) }
  const societe = company?.raison_sociale ?? company?.nom

  return (
    <header className="flex items-center justify-between h-16 px-space-xl lg:pl-64 w-full fixed top-0 left-0 z-30 bg-surface border-b border-border shadow-sm">
      <div className="flex items-center gap-4 lg:gap-6 min-w-0">
        <button className="lg:hidden p-2 text-muted hover:text-ink" aria-label="Menu" onClick={onBurger}><Icon name="menu" className="text-[22px]" /></button>
        {/* Fil d'Ariane contextuel */}
        <div className="hidden md:flex items-center gap-2 text-body-md min-w-0">
          <button onClick={() => navigate('/portefeuille')} className="text-primary font-bold hover:underline whitespace-nowrap">Portefeuille</button>
          {societe && <>
            <span className="text-muted">›</span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-label-md font-label-md bg-surface-container text-ink border border-border truncate max-w-[16rem]">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary shrink-0"></span>{societe}
            </span>
          </>}
        </div>
        {/* Recherche globale */}
        <form onSubmit={submit} className="relative w-56 xl:w-80 hidden sm:block">
          <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-muted text-[18px]" />
          <input value={q} onChange={(e) => setQ(e.target.value)} className="w-full pl-9 pr-4 py-1.5 text-body-md bg-surface-container-low border border-border rounded-xl focus:outline-none focus:border-secondary focus:ring-1 focus:ring-secondary transition-all" placeholder="Rechercher une société, un salarié…" type="text" />
        </form>
      </div>
      <div className="flex items-center gap-3 lg:gap-4">
        <div className="hidden lg:flex items-center gap-2 bg-surface-container-low px-3 py-1 rounded-lg border border-border">
          <span className="text-label-md text-muted">Cycle en cours :</span>
          <span className="text-label-md font-bold text-ink">{cycle}</span>
          <span className="w-2 h-2 rounded-full bg-warning animate-pulse" title="Échéances proches"></span>
        </div>
        <div className="hidden md:flex items-center gap-1">
          <button className="relative p-2 text-muted hover:text-ink hover:bg-surface-container rounded-lg transition-colors" title="Notifications">
            <Icon name="notifications" className="text-[20px]" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-danger rounded-full"></span>
          </button>
        </div>
        <div className="h-6 w-px bg-border hidden md:block"></div>
        <button onClick={() => navigate('/portefeuille')} className="hidden sm:block px-3.5 py-1.5 bg-surface text-ink border border-border font-label-md text-label-md rounded-xl hover:bg-surface-container transition-colors shadow-sm">Dossiers</button>
        <button onClick={() => navigate(companyId ? `/c/${companyId}/paie` : '/portefeuille')} className="flex items-center gap-1.5 px-4 py-1.5 bg-secondary-fixed text-ink font-extrabold text-label-md rounded-xl hover:opacity-90 transition-all shadow-sm">
          <Icon name="play_arrow" className="text-[16px]" /><span>Lancer la paie</span>
        </button>
      </div>
    </header>
  )
}

export default function AppShell() {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)
  return (
    <div className="min-h-screen bg-background">
      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={close} />}
      <div className={`${open ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0 transition-transform`}>
        <Sidebar onNavigate={close} />
      </div>
      <Topbar onBurger={() => setOpen((v) => !v)} />
      <main className="lg:ml-60 pt-16 min-h-screen">
        <div className="p-space-xl max-w-[1600px] mx-auto flex flex-col gap-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
