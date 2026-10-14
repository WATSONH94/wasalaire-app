import { NavLink, Outlet, useParams } from 'react-router-dom'

export default function CompanyLayout() {
  const { companyId } = useParams()
  const base = `/c/${companyId}`
  return (
    <div>
      <nav className="app-nav" style={{ marginBottom: 16 }}>
        <NavLink to={`${base}/salaries`}>Salariés</NavLink>
        <NavLink to={`${base}/paie`}>Paie</NavLink>
        <NavLink to={`${base}/reporting`}>Reporting</NavLink>
      </nav>
      <Outlet />
    </div>
  )
}
