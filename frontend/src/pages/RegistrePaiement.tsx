import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type PaymentRegister, type Run } from '../api'
import { Badge, Card, Icon } from '../stitch'

const MOIS = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
const METHODE: Record<string, string> = { especes: 'Espèces', mobile_money: 'Mobile Money', virement: 'Virement', cheque: 'Chèque' }
const STATUT: Record<string, { label: string; tone: 'warning' | 'secondary' | 'success' | 'danger' }> = {
  a_envoyer: { label: 'À envoyer', tone: 'warning' },
  envoye: { label: 'Envoyé', tone: 'secondary' },
  confirme: { label: 'Confirmé', tone: 'success' },
  echoue: { label: 'Échec', tone: 'danger' },
}

export default function RegistrePaiement() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [sel, setSel] = useState<Run | null>(null)
  const [reg, setReg] = useState<PaymentRegister | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.companyRuns(cid)
      .then((r) => {
        const actifs = r.runs.filter((x) => x.actif !== false)
        setRuns(actifs)
        const first = actifs.find((x) => x.statut === 'cloturee') ?? actifs[0] ?? null
        if (first) setSel(first)
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }, [cid])

  useEffect(() => {
    if (!sel) { setReg(null); return }
    setLoading(true); setReg(null); setError(null)
    api.paymentRegister(sel.run_id)
      .then(setReg)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
      .finally(() => setLoading(false))
  }, [sel])

  const periode = reg ? `${MOIS[reg.periode.mois]} ${reg.periode.annee}` : ''
  const vide = reg != null && reg.nb_paiements === 0

  function exporter() {
    if (!reg || vide) return
    const rows = [
      ['# Registre de paiement — Code du Travail art. 224-226', periode, reg.societe.raison_sociale ?? ''],
      ['N° employeur CNSS', reg.societe.num_employeur_cnss ?? '', 'IFU', reg.societe.ifu ?? ''],
      ['Matricule', 'Nom', 'N° CNSS', 'Net payé', 'Méthode', 'Statut', 'Référence', 'Date'],
      ...reg.lignes.map((l) => [l.matricule, l.nom, l.num_cnss, String(Math.round(l.net_paye)), METHODE[l.methode] ?? l.methode, STATUT[l.statut]?.label ?? l.statut, l.reference, l.date_paiement]),
      ['', 'TOTAL PAYÉ', '', String(reg.total_paye)],
    ]
    const csv = rows.map((r) => r.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(';')).join('\r\n')
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a'); a.href = url; a.download = `registre-paiement-${reg.periode.annee}-${String(reg.periode.mois).padStart(2, '0')}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6 print:hidden">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Registre de paiement</h2>
              <Badge tone="secondary" icon="gavel">Code du Travail · art. 224-226</Badge>
            </div>
            <p className="text-body-md text-muted mt-1 max-w-2xl">Preuve légale des paiements de salaires effectués : net payé, méthode, date et statut par salarié, à partir des ordres de décaissement.</p>
          </div>
          <button onClick={exporter} disabled={!reg || vide} className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container shadow-sm disabled:opacity-50 shrink-0"><Icon name="download" className="text-[18px]" /> Exporter (CSV)</button>
        </div>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {runs == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : runs.length === 0 ? (
        <Card className="p-10 text-center"><Icon name="gavel" className="text-[40px] text-outline-variant" /><p className="text-muted mt-2">Aucun cycle de paie.</p></Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
          <Card className="p-3 lg:col-span-1 h-fit print:hidden">
            <div className="text-label-md font-bold text-muted uppercase px-2 py-1">Cycles</div>
            <div className="flex flex-col gap-1">
              {runs.map((r) => (
                <button key={r.run_id} onClick={() => setSel(r)}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-colors ${sel?.run_id === r.run_id ? 'bg-secondary/10 text-secondary' : 'hover:bg-surface-container-low text-ink'}`}>
                  <span className="font-bold capitalize">{MOIS[r.mois]} {r.annee}</span>
                  <Badge tone={r.statut === 'cloturee' ? 'success' : 'neutral'}>{r.statut === 'cloturee' ? 'Clôturé' : r.statut}</Badge>
                </button>
              ))}
            </div>
          </Card>

          <div className="lg:col-span-3">
            {loading ? (
              <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement du registre…</div>
            ) : !reg ? (
              <Card className="p-8 text-center text-muted">Sélectionnez un cycle.</Card>
            ) : vide ? (
              <Card className="p-8 text-center text-muted">Aucun paiement enregistré pour ce cycle. Le registre se remplit après le décaissement des salaires (étape « Décaissement » du cycle de paie).</Card>
            ) : (
              <Card className="p-0 overflow-hidden">
                <div className="p-5 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h3 className="text-subtitle-md font-bold text-ink">{reg.societe.raison_sociale}</h3>
                    <span className="text-label-md text-muted">N° employeur CNSS : {reg.societe.num_employeur_cnss || '—'} · <span className="capitalize">{periode}</span> · {reg.nb_paiements} paiement{reg.nb_paiements > 1 ? 's' : ''}</span>
                  </div>
                  <Badge tone="neutral" icon="verified">Registre légal</Badge>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-body-sm">
                    <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wide">
                      <th className="py-3 px-4">Salarié</th><th className="py-3 px-3">N° CNSS</th>
                      <th className="py-3 px-3 text-right">Net payé</th><th className="py-3 px-3">Méthode</th>
                      <th className="py-3 px-3">Statut</th><th className="py-3 px-4">Date</th>
                    </tr></thead>
                    <tbody className="divide-y divide-border text-ink">
                      {reg.lignes.map((l, i) => (
                        <tr key={i} className="hover:bg-primary-fixed/10">
                          <td className="py-2.5 px-4"><span className="font-bold">{l.nom}</span> <span className="text-muted font-mono text-label-md">{l.matricule}</span></td>
                          <td className="py-2.5 px-3 font-mono text-muted">{l.num_cnss || '—'}</td>
                          <td className="py-2.5 px-3 text-right tabular-nums font-bold text-secondary">{fcfa(l.net_paye)}</td>
                          <td className="py-2.5 px-3">{METHODE[l.methode] ?? l.methode}</td>
                          <td className="py-2.5 px-3"><Badge tone={STATUT[l.statut]?.tone ?? 'neutral'}>{STATUT[l.statut]?.label ?? l.statut}</Badge></td>
                          <td className="py-2.5 px-4 tabular-nums text-muted">{l.date_paiement}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot><tr className="bg-primary/5 border-t-2 border-primary font-extrabold text-ink">
                      <td className="py-3 px-4" colSpan={2}>TOTAL PAYÉ ({reg.nb_paiements})</td>
                      <td className="py-3 px-3 text-right tabular-nums text-secondary">{fcfa(reg.total_paye)}</td>
                      <td className="py-3 px-4" colSpan={3}></td>
                    </tr></tfoot>
                  </table>
                </div>
                <p className="p-4 text-label-md text-muted flex items-start gap-1.5"><Icon name="info" className="text-[16px] mt-0.5" />Registre conforme aux art. 224-226 du Code du Travail (preuve des paiements). Les statuts reflètent l'état des ordres de décaissement.</p>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
