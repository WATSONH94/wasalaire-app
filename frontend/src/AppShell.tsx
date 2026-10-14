import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from './auth'
import { Brand, Button } from './ui'

export default function AppShell() {
  const { session, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)

  return (
    <div className="console">
      {open && <div className="scrim" onClick={close} />}
      <aside className={`sidebar${open ? ' open' : ''}`}>
        <div className="logo"><Brand height={30} variant="blanc" /></div>
        <NavLink to="/" end onClick={close}>Sociétés</NavLink>
        <div className="sep" />
        <div className="foot">
          {session && session.roles.length > 0 && (
            <div style={{ color: 'rgba(255,255,255,0.6)', fontSize: '.74rem', padding: '0 12px 8px' }}>
              {session.roles.join(' · ')}
            </div>
          )}
          <Button variant="ghost" className="btn-sm" onClick={logout} style={{ width: '100%' }}>Déconnexion</Button>
        </div>
      </aside>

      <div className="console-main">
        <div className="topbar">
          <button className="burger" aria-label="Menu" onClick={() => setOpen((v) => !v)}>☰</button>
          <div className="ctx-select"><span>Espace</span> <b>WaSalaire</b></div>
          <span />
        </div>
        <div className="content"><Outlet /></div>
      </div>
    </div>
  )
}
