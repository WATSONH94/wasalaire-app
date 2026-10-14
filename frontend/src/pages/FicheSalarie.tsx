import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Employee } from '../api'
import { Badge, Card, Icon } from '../stitch'

const PAIEMENT: Record<string, string> = {
  especes: 'Espèces',
  virement: 'Virement bancaire',
  mobile_money: 'Mobile Money',
  momo: 'Mobile Money',
}

export default function FicheSalarie() {
  const { companyId, empId } = useParams()
  const cid = companyId as string
  const [emp, setEmp] = useState<Employee | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.employees(cid)
      .then((r) => setEmp(r.employes.find((e) => e.id === empId) ?? null))
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
      .finally(() => setLoading(false))
  }, [cid, empId])

  if (loading) return <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
  if (error) return <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>
  if (!emp) return (
    <Card className="p-10 text-center">
      <Icon name="person_off" className="text-[40px] text-outline-variant" />
      <p className="text-muted mt-2">Salarié introuvable.</p>
      <Link to={`/c/${cid}/salaries`} className="text-secondary font-bold hover:underline mt-2 inline-block">← Retour à l’équipe</Link>
    </Card>
  )

  return (
    <div className="flex flex-col gap-5">
      {/* En-tête fiche */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link to={`/c/${cid}/salaries`} className="p-2 rounded-lg text-muted hover:text-ink hover:bg-surface-container" title="Retour">
            <Icon name="arrow_back" className="text-[20px]" />
          </Link>
          <div className="w-14 h-14 rounded-2xl bg-primary text-surface-container-lowest flex items-center justify-center text-subtitle-lg font-extrabold">
            {emp.nom.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <h1 className="text-headline-md font-headline-md text-ink">{emp.nom}</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-label-md text-muted font-mono bg-surface-container px-1.5 rounded">{emp.matricule}</span>
              <Badge tone="success" icon="check_circle">Actif</Badge>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Rémunération */}
        <Card className="p-6 flex flex-col gap-4">
          <h3 className="text-subtitle-md font-bold text-ink flex items-center gap-2"><Icon name="payments" className="text-secondary" /> Rémunération</h3>
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-label-md text-muted">Salaire brut de base</span>
              <span className="font-extrabold text-ink tabular-nums">{fcfa(emp.salaire_base ?? undefined)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-label-md text-muted">Méthode de paiement</span>
              <span className="font-semibold text-ink">{PAIEMENT[emp.methode_paiement ?? ''] ?? emp.methode_paiement ?? '—'}</span>
            </div>
          </div>
        </Card>

        {/* Contrat */}
        <Card className="p-6 flex flex-col gap-4">
          <h3 className="text-subtitle-md font-bold text-ink flex items-center gap-2"><Icon name="description" className="text-secondary" /> Contrat</h3>
          <div className="flex items-center justify-between">
            <span className="text-label-md text-muted">Matricule</span>
            <span className="font-semibold text-ink font-mono">{emp.matricule}</span>
          </div>
          <p className="text-label-md text-muted">Détails du contrat (type, dates, poste, CNSS) et documents associés : module en cours de portage.</p>
        </Card>

        {/* Paie récente */}
        <Card className="p-6 flex flex-col gap-3">
          <h3 className="text-subtitle-md font-bold text-ink flex items-center gap-2"><Icon name="history" className="text-secondary" /> Historique paie</h3>
          <div className="flex-1 flex flex-col items-center justify-center text-center py-6 text-muted">
            <Icon name="receipt_long" className="text-[32px] text-outline-variant" />
            <p className="text-label-md mt-1">L’historique des bulletins apparaîtra après le calcul d’un cycle.</p>
          </div>
          <Link to={`/c/${cid}/paie`} className="text-secondary font-bold text-label-md hover:underline inline-flex items-center gap-1">
            Aller au cycle de paie <Icon name="arrow_forward" className="text-[14px]" />
          </Link>
        </Card>
      </div>
    </div>
  )
}
