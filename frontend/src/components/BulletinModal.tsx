import { fcfa, type Payslip } from '../api'
import { Icon } from '../stitch'

const MOIS = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

function Row({ label, base, montant, tone }: { label: string; base?: number; montant: number; tone?: 'gain' | 'retenue' }) {
  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-2 px-3 text-ink">{label}</td>
      <td className="py-2 px-3 text-right tabular-nums text-muted">{base != null ? fcfa(base) : ''}</td>
      <td className={`py-2 px-3 text-right tabular-nums font-semibold ${tone === 'retenue' ? 'text-danger' : 'text-ink'}`}>
        {tone === 'retenue' ? '- ' : ''}{fcfa(montant)}
      </td>
    </tr>
  )
}

export default function BulletinModal({
  payslip, mois, annee, societe, onClose,
}: {
  payslip: Payslip
  mois: number
  annee: number
  societe?: string
  onClose: () => void
}) {
  const d = payslip.detail ?? {}
  const brut = d.brut ?? payslip.brut
  const cnssSal = d.cnss_sal ?? 0
  const its = d.its ?? 0
  const net = d.net_a_payer ?? d.net ?? payslip.net
  const cnssPat = d.cnss_pat ?? 0
  const vps = d.vps ?? 0
  const amoPat = d.amo_pat ?? 0
  const cout = d.cout_employeur ?? payslip.cout_employeur
  const gains = d.lignes?.gains ?? [{ libelle: 'Salaire brut', montant: brut }]
  const retenues = d.lignes?.retenues ?? [
    { libelle: 'Cotisation CNSS (part salariale)', montant: cnssSal },
    { libelle: 'Impôt sur Traitements & Salaires (ITS)', montant: its },
  ]

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-start justify-center overflow-y-auto p-4 print:p-0 print:bg-white" onClick={onClose}>
      <div className="bg-surface rounded-2xl shadow-xl w-full max-w-2xl my-6 print:my-0 print:shadow-none" onClick={(e) => e.stopPropagation()}>
        {/* Barre d'actions (masquée à l'impression) */}
        <div className="flex items-center justify-between p-4 border-b border-border print:hidden">
          <h3 className="text-subtitle-md font-bold text-ink">Bulletin de paie</h3>
          <div className="flex items-center gap-2">
            <button onClick={() => window.print()} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-secondary-fixed text-ink font-bold text-label-md rounded-lg hover:bg-secondary-fixed-dim">
              <Icon name="print" className="text-[18px]" /> Imprimer
            </button>
            <button onClick={onClose} className="p-1.5 text-muted hover:text-ink rounded-lg" title="Fermer"><Icon name="close" /></button>
          </div>
        </div>

        {/* Corps A4 */}
        <div className="p-8" id="bulletin-print">
          <div className="flex items-start justify-between pb-4 border-b-2 border-primary">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-primary text-surface-container-lowest flex items-center justify-center font-extrabold">W</div>
              <div>
                <div className="text-subtitle-lg font-extrabold text-primary">{societe ?? 'Société'}</div>
                <div className="text-label-md text-muted">Bulletin de paie — conforme Bénin (DGI / CNSS)</div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-label-md text-muted">Période</div>
              <div className="font-bold text-ink capitalize">{MOIS[mois]} {annee}</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 py-4">
            <div>
              <div className="text-label-md text-muted">Salarié</div>
              <div className="font-bold text-ink">{payslip.nom}</div>
            </div>
            <div className="text-right">
              <div className="text-label-md text-muted">Matricule</div>
              <div className="font-bold text-ink font-mono">{payslip.matricule ?? '—'}</div>
            </div>
          </div>

          <table className="w-full text-body-md border border-border rounded-lg overflow-hidden">
            <thead>
              <tr className="bg-surface-container-low text-label-md font-bold text-muted">
                <th className="py-2 px-3 text-left">Rubrique</th>
                <th className="py-2 px-3 text-right">Base</th>
                <th className="py-2 px-3 text-right">Montant</th>
              </tr>
            </thead>
            <tbody>
              <tr className="bg-surface"><td colSpan={3} className="py-1.5 px-3 text-label-md font-bold text-primary uppercase">Gains</td></tr>
              {gains.map((g, i) => (
                <Row key={`g${i}`} label={g.libelle} montant={g.montant} tone="gain" />
              ))}
              <tr className="bg-surface"><td colSpan={3} className="py-1.5 px-3 text-label-md font-bold text-primary uppercase">Retenues salariales</td></tr>
              {retenues.map((r, i) => {
                const base = /cnss/i.test(r.libelle) ? d.assiette_cnss
                  : /its|traitements/i.test(r.libelle) ? d.base_its : undefined
                return <Row key={`r${i}`} label={r.libelle} base={base} montant={r.montant} tone="retenue" />
              })}
            </tbody>
            <tfoot>
              <tr className="bg-primary/5 border-t-2 border-primary">
                <td className="py-3 px-3 font-extrabold text-primary" colSpan={2}>Net à payer</td>
                <td className="py-3 px-3 text-right font-extrabold text-secondary text-subtitle-md tabular-nums">{fcfa(net)}</td>
              </tr>
            </tfoot>
          </table>

          <div className="mt-4 p-3 rounded-lg bg-surface-container-low border border-border">
            <div className="text-label-md font-bold text-muted uppercase mb-2">Charges patronales (employeur)</div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-body-md">
              <div className="flex justify-between"><span className="text-muted">CNSS patronale</span><span className="tabular-nums font-semibold">{fcfa(cnssPat)}</span></div>
              <div className="flex justify-between"><span className="text-muted">Versement Patronal (VPS)</span><span className="tabular-nums font-semibold">{fcfa(vps)}</span></div>
              <div className="flex justify-between"><span className="text-muted">AMO patronale</span><span className="tabular-nums font-semibold">{fcfa(amoPat)}</span></div>
              <div className="flex justify-between border-t border-border pt-1 mt-1"><span className="font-bold text-ink">Coût employeur</span><span className="tabular-nums font-extrabold text-ink">{fcfa(cout)}</span></div>
            </div>
          </div>

          <p className="mt-4 text-label-md text-muted">Document calculé par WaSalaire. Les montants ITS/VPS et cotisations CNSS suivent les barèmes béninois intégrés.</p>
        </div>
      </div>
    </div>
  )
}
