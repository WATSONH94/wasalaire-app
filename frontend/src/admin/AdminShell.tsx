import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth'
import { Icon } from '../stitch'

const NAV: { label: string; icon: string; to: string }[] = [
  { label: 'Tableau de bord', icon: 'monitoring', to: '/' },
  { label: 'Organisations', icon: 'domain', to: '/organizations' },
  { label: 'Utilisateurs internes', icon: 'shield_person', to: '/internal-users' },
  { label: 'Utilisateurs clients', icon: 'group', to: '/client-users' },
  { label: 'Abonnements', icon: 'card_membership', to: '/subscriptions' },
  { label: 'Référentiels', icon: 'gavel', to: '/referentials' },
  { label: 'Audit & sécurité', icon: 'policy', to: '/audit' },
  { label: 'Supervision', icon: 'dns', to: '/supervision' },
  { label: 'Support', icon: 'support_agent', to: '/support' },
  { label: 'Paramètres', icon: 'settings', to: '/settings' },
]

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super-administrateur',
  admin_plateforme: 'Admin plateforme',
  support: 'Support technique',
  conformite: 'Responsable conformité',
  commercial: 'Responsable commercial',
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { session, logout } = useAuth()
  const role = session?.platform_role && session.platform_role !== 'none' ? ROLE_LABELS[session.platform_role] ?? session.platform_role : '—'

  return (
    <aside className="fixed top-0 left-0 h-screen w-64 z-40 bg-ink text-white flex flex-col justify-between p-space-md">
      <div className="flex flex-col gap-space-lg min-h-0">
        <div className="flex items-center gap-3 px-space-sm pt-space-xs">
          <div className="w-10 h-10 rounded-xl bg-warning flex items-center justify-center shadow-sm">
            <span className="text-ink font-extrabold text-subtitle-lg">W</span>
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-white font-extrabold text-subtitle-md">WaSalaire</span>
            <span className="text-warning text-[10px] font-bold tracking-wider">ADMIN · INTERNE</span>
          </div>
        </div>

        <nav className="flex flex-col gap-1 overflow-y-auto">
          {NAV.map((item) => (
            <NavLink
              key={item.label}
              to={item.to}
              end={item.to === '/'}
              onClick={onNavigate}
              className={({ isActive }) =>
                `flex items-center gap-space-md px-space-md py-space-sm rounded-xl font-medium transition-colors duration-150 ${
                  isActive ? 'bg-warning text-ink' : 'text-white/70 hover:text-white hover:bg-white/10'
                }`
              }
            >
              <Icon name={item.icon} className="text-[20px]" />
              <span className="text-label-lg font-label-lg">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="flex flex-col gap-3 pt-3 border-t border-white/15">
        <a href="/?surface=client" className="flex items-center gap-2 text-white/70 hover:text-white text-label-md transition-colors px-1">
          <Icon name="swap_horiz" className="text-[18px]" /> Aller à l’app client
        </a>
        <div className="flex items-center justify-between gap-2 px-1 py-1 rounded-lg bg-white/5">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-full bg-warning/20 text-warning flex items-center justify-center text-xs font-bold">
              {(session?.email ?? 'WS').slice(0, 2).toUpperCase()}
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-label-md text-white truncate">{session?.email ?? 'Interne'}</span>
              <span className="text-[10px] text-white/60 truncate">{role}</span>
            </div>
          </div>
          <button onClick={logout} className="text-white/60 hover:text-white p-1" title="Déconnexion"><Icon name="logout" className="text-[18px]" /></button>
        </div>
      </div>
    </aside>
  )
}

export default function AdminShell() {
  const [open, setOpen] = useState(false)
  return (
    <div className="min-h-screen bg-background">
      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} />}
      <div className={`${open ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0 transition-transform`}>
        <Sidebar onNavigate={() => setOpen(false)} />
      </div>
      <header className="flex items-center justify-between h-14 px-space-xl lg:pl-72 w-full fixed top-0 left-0 z-30 bg-warning/10 border-b border-warning/30">
        <div className="flex items-center gap-3">
          <button className="lg:hidden p-2 text-muted" aria-label="Menu" onClick={() => setOpen((v) => !v)}><Icon name="menu" /></button>
          <span className="inline-flex items-center gap-1.5 text-label-md font-bold text-warning uppercase tracking-wide">
            <Icon name="warning" className="text-[16px]" /> Espace interne éditeur — accès aux données clients tracé
          </span>
        </div>
      </header>
      <main className="lg:ml-64 pt-14 min-h-screen">
        <div className="p-space-xl max-w-[1600px] mx-auto flex flex-col gap-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
