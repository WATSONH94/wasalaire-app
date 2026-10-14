import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from './auth'
import AppShell from './AppShell'
import CompanyLayout from './CompanyLayout'
import Login from './pages/Login'
import Companies from './pages/Companies'
import Employees from './pages/Employees'
import Payroll from './pages/Payroll'
import Reporting from './pages/Reporting'

function RequireAuth({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth()
  if (loading) return <div className="centered"><span className="spinner" /></div>
  if (!session) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><AppShell /></RequireAuth>}>
        <Route index element={<Companies />} />
        <Route path="c/:companyId" element={<CompanyLayout />}>
          <Route index element={<Navigate to="salaries" replace />} />
          <Route path="salaries" element={<Employees />} />
          <Route path="paie" element={<Payroll />} />
          <Route path="reporting" element={<Reporting />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
