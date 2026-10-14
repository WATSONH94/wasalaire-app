import { Link } from 'react-router-dom'
import { Card, Icon, PageHeader } from '../stitch'

// Écran en cours de portage depuis les maquettes Stitch. Honnête : aucune donnée simulée.
export default function ComingSoon({
  title,
  icon,
  description,
}: {
  title: string
  icon: string
  description: string
}) {
  return (
    <>
      <PageHeader title={title} />
      <Card className="p-10 flex flex-col items-center text-center gap-3">
        <div className="w-16 h-16 rounded-2xl bg-surface-container flex items-center justify-center text-primary">
          <Icon name={icon} className="text-[32px]" />
        </div>
        <h2 className="text-subtitle-lg font-subtitle-lg text-ink">Module en cours de déploiement</h2>
        <p className="text-body-md text-muted max-w-md">{description}</p>
        <Link
          to="/"
          className="mt-2 px-4 py-2 bg-surface border border-border rounded-xl text-label-lg font-bold text-ink hover:bg-surface-container transition-colors inline-flex items-center gap-1.5"
        >
          <Icon name="arrow_back" className="text-[18px]" /> Retour au tableau de bord
        </Link>
      </Card>
    </>
  )
}
