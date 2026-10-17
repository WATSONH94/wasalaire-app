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
import Declarations from './pages/Declarations'
import Payroll from './pages/Payroll'
import Reporting from './pages/Reporting'
import Comptabilite from './pages/Comptabilite'
import Documents from './pages/Documents'
import SoldeToutCompte from './pages/SoldeToutCompte'
import RegistrePaiement from './pages/RegistrePaiement'
import WaDocs from './pages/WaDocs'
import Rapprochement from './pages/Rapprochement'
import Conges from './pages/Conges'
import Structure from './pages/Structure'
import Campagnes from './pages/Campagnes'
import Conformite from './pages/Conformite'
import Parametres from './pages/Parametres'

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
        <Route path="campagnes" element={<Campagnes />} />
        <Route path="mon-compte" element={<MonCompte />} />
        <Route path="nouvelle-societe" element={<Onboarding />} />
        <Route path="conformite" element={<Conformite />} />
        <Route path="parametres" element={<Parametres />} />
        <Route path="c/:companyId" element={<CompanyLayout />}>
          <Route index element={<Navigate to="salaries" replace />} />
          <Route path="salaries" element={<Employees />} />
          <Route path="salaries/:empId" element={<FicheSalarie />} />
          <Route path="paie" element={<Payroll />} />
          <Route path="reporting" element={<Reporting />} />
          <Route path="declarations" element={<Declarations />} />
          <Route path="comptabilite" element={<Comptabilite />} />
          <Route path="rapprochement" element={<Rapprochement />} />
          <Route path="documents" element={<Documents />} />
          <Route path="registre-paiement" element={<RegistrePaiement />} />
          <Route path="wadocs" element={<WaDocs />} />
          <Route path="solde-tout-compte" element={<SoldeToutCompte />} />
          <Route path="conges" element={<Conges />} />
          <Route path="structure" element={<Structure />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
