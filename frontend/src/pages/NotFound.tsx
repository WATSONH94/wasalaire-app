import { Link, useNavigate } from 'react-router-dom'
import { Card, Icon } from '../stitch'

export default function NotFound() {
  const nav = useNavigate()
  return (
    <div className="flex items-center justify-center py-16">
      <Card className="p-10 max-w-lg w-full text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-warm-sand/30 text-warning mb-4">
          <Icon name="explore_off" className="text-[36px]" />
        </div>
        <div className="text-headline-lg font-extrabold text-ink tracking-tight">404</div>
        <h2 className="text-subtitle-lg font-bold text-ink mt-1">Page introuvable</h2>
        <p className="text-body-md text-muted mt-2 max-w-sm mx-auto">
          La page demandée n'existe pas ou a été déplacée. Vérifiez l'adresse ou revenez à votre tableau de bord.
        </p>
        <div className="flex items-center justify-center gap-2 mt-6">
          <button onClick={() => nav(-1)} className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-surface-container text-ink font-bold rounded-xl hover:bg-surface-container-high">
            <Icon name="arrow_back" className="text-[18px]" /> Retour
          </button>
          <Link to="/" className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container shadow-sm">
            <Icon name="dashboard" className="text-[18px]" /> Tableau de bord
          </Link>
        </div>
      </Card>
    </div>
  )
}
