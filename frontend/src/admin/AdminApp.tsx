import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from '../auth'
import { Card, Icon } from '../stitch'
import AdminShell from './AdminShell'
import AdminDashboard from './pages/AdminDashboard'
import Organizations from './pages/Organizations'
import InternalUsers from './pages/InternalUsers'
import ClientUsers from './pages/ClientUsers'
import Audit from './pages/Audit'
import AdminPlaceholder from './pages/AdminPlaceholder'
import Referentials from './pages/Referentials'
import Abonnements from '../pages/admin/Abonnements'
import Login from '../pages/Login'

function RequireInternal({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth()
  if (loading) return <div className="centered"><span className="spinner" /></div>
  if (!session) return <Navigate to="/login" replace />
  const internal = session.platform_role && session.platform_role !== 'none'
  if (!internal) {
    return (
      <div className="centered p-6">
        <Card className="p-10 max-w-md text-center flex flex-col items-center gap-3">
          <div className="w-16 h-16 rounded-2xl bg-danger/10 text-danger flex items-center justify-center"><Icon name="block" className="text-[32px]" /></div>
          <h1 className="text-subtitle-lg font-subtitle-lg text-ink">Accès réservé à l’équipe WaSalaire</h1>
          <p className="text-body-md text-muted">Cet espace est l’administration interne de l’éditeur. Votre compte n’a pas de rôle interne.</p>
          <a href="/?surface=client" className="mt-2 px-4 py-2 bg-primary text-white rounded-xl font-bold text-label-lg">Aller à l’application</a>
        </Card>
      </div>
    )
  }
  return <>{children}</>
}

export default function AdminApp() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireInternal><AdminShell /></RequireInternal>}>
        <Route index element={<AdminDashboard />} />
        <Route path="organizations" element={<Organizations />} />
        <Route path="internal-users" element={<InternalUsers />} />
        <Route path="client-users" element={<ClientUsers />} />
        <Route path="subscriptions" element={<Abonnements />} />
        <Route path="referentials" element={<Referentials />} />
        <Route path="audit" element={<Audit />} />
        <Route path="supervision" element={<AdminPlaceholder title="Supervision technique" icon="dns" description="État des services, API, jobs, sauvegardes et déploiements — relié à l’infrastructure réelle (en cours)." />} />
        <Route path="support" element={<AdminPlaceholder title="Support client" icon="support_agent" description="Tickets, incidents et suivi des demandes clients, avec interventions encadrées et tracées (en cours)." />} />
        <Route path="settings" element={<AdminPlaceholder title="Paramètres globaux" icon="settings" description="Configuration de l’éditeur : offres, notifications, modèles, feature flags (secrets jamais affichés) — en cours." />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
