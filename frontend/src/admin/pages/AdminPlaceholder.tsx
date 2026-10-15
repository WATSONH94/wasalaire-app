import { Card, Icon, PageHeader } from '../../stitch'

export default function AdminPlaceholder({ title, icon, description }: { title: string; icon: string; description: string }) {
  return (
    <>
      <PageHeader title={title} />
      <Card className="p-10 flex flex-col items-center text-center gap-3">
        <div className="w-16 h-16 rounded-2xl bg-warning/10 text-warning flex items-center justify-center"><Icon name={icon} className="text-[32px]" /></div>
        <h2 className="text-subtitle-lg font-subtitle-lg text-ink">Module interne en construction</h2>
        <p className="text-body-md text-muted max-w-md">{description}</p>
      </Card>
    </>
  )
}
