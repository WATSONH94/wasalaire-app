import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from './auth'
import AppShell from './AppShell'
import CompanyLayout from './CompanyLayout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Companies from './pages/Companies'
import MonCompte from './pages/MonCompte'
import Onboarding from './pages/Onboarding'
import Employees from './pages/Employees'
import FicheSalarie from './pages/FicheSalarie'
import Payroll from './pages/Payroll'
import Reporting from './pages/Reporting'
import ComingSoon from './pages/ComingSoon'
import Utilisateurs from './pages/admin/Utilisateurs'
import Abonnements from './pages/admin/Abonnements'

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
        <Route index element={<Dashboard />} />
        <Route path="portefeuille" element={<Companies />} />
        <Route path="mon-compte" element={<MonCompte />} />
        <Route path="nouvelle-societe" element={<Onboarding />} />
        <Route path="admin/utilisateurs" element={<Utilisateurs />} />
        <Route path="admin/abonnements" element={<Abonnements />} />
        <Route
          path="conformite"
          element={<ComingSoon title="Conformité" icon="verified_user" description="Calendrier réglementaire DGI & CNSS, suivi des barèmes et contrôles de conformité — en cours de portage depuis les maquettes." />}
        />
        <Route
          path="parametres"
          element={<ComingSoon title="Paramètres" icon="settings" description="Gestion du compte, des utilisateurs, des rôles et des préférences du cabinet — en cours de portage." />}
        />
        <Route path="c/:companyId" element={<CompanyLayout />}>
          <Route index element={<Navigate to="salaries" replace />} />
          <Route path="salaries" element={<Employees />} />
          <Route path="salaries/:empId" element={<FicheSalarie />} />
          <Route path="paie" element={<Payroll />} />
          <Route path="reporting" element={<Reporting />} />
          <Route
            path="declarations"
            element={<ComingSoon title="Déclarations" icon="description" description="Déclarations ITS/VPS (DGI) et cotisations CNSS générées à partir des cycles calculés — en cours de portage." />}
          />
          <Route
            path="comptabilite"
            element={<ComingSoon title="Comptabilité" icon="account_balance" description="Écritures de paie au format SYSCOHADA et export comptable — en cours de portage." />}
          />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
