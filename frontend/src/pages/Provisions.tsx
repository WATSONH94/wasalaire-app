import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Provisions as Prov } from '../api'
import { Badge, Card, Icon } from '../stitch'

export default function Provisions() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [data, setData] = useState<Prov | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true); setError(null)
    api.provisions(cid).then(setData).catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau')).finally(() => setLoading(false))
  }, [cid])

  function exporter() {
    if (!data) return
    const rows = [
      ['# Provisions sociales (indicatives)', String(data.annee)],
      ['Matricule', 'Nom', 'Ancienneté (ans)', 'Jours CP', 'Provision congés payés', 'Engagement IFC'],
      ...data.lignes.map((l) => [l.matricule, l.nom, String(l.anciennete_ans), String(l.jours_cp), String(l.provision_conges), String(l.engagement_ifc)]),
      ['', 'TOTAUX', '', '', String(data.total_provision_conges), String(data.total_engagement_ifc)],
    ]
    const csv = rows.map((r) => r.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(';')).join('\r\n')
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a'); a.href = url; a.download = `provisions-${data.annee}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Provisions congés payés &amp; IFC</h2>
              <Badge tone="warning" icon="info">Estimation indicative</Badge>
            </div>
            <p className="text-body-md text-muted mt-1 max-w-2xl">Engagements sociaux par salarié actif : provision pour congés payés acquis non pris et engagement d'indemnité de fin de carrière (IFC) à date.</p>
          </div>
          <button onClick={exporter} disabled={!data || data.effectif === 0} className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container shadow-sm disabled:opacity-50 shrink-0"><Icon name="download" className="text-[18px]" /> Exporter (CSV)</button>
        </div>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {loading ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Calcul des provisions…</div>
      ) : data ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card className="p-5">
              <div className="flex items-center justify-between"><span className="text-label-md text-muted">Provision congés payés</span><Icon name="beach_access" className="text-muted" /></div>
              <div className="text-headline-sm font-extrabold text-ink tabular-nums mt-2">{fcfa(data.total_provision_conges)}</div>
              <div className="text-label-md text-muted mt-1">Jours acquis non pris × 1/30e</div>
            </Card>
            <Card className="p-5">
              <div className="flex items-center justify-between"><span className="text-label-md text-muted">Engagement IFC</span><Icon name="savings" className="text-muted" /></div>
              <div className="text-headline-sm font-extrabold text-ink tabular-nums mt-2">{fcfa(data.total_engagement_ifc)}</div>
              <div className="text-label-md text-muted mt-1">Indemnité de fin de carrière à date</div>
            </Card>
            <Card className="p-5">
              <div className="flex items-center justify-between"><span className="text-label-md text-muted">Effectif actif</span><Icon name="badge" className="text-muted" /></div>
              <div className="text-headline-sm font-extrabold text-ink tabular-nums mt-2">{data.effectif}</div>
              <div className="text-label-md text-muted mt-1">Exercice {data.annee}</div>
            </Card>
          </div>

          <div className="p-3 rounded-xl bg-warm-sand/20 border border-warm-sand/50 text-ink text-label-md flex items-start gap-2">
            <Icon name="warning" className="text-warning mt-0.5" />
            <span><strong>Estimation de gestion, non certifiée.</strong> La provision IFC est l'engagement à date (non actualisé) ; une évaluation actuarielle actualisée relève d'un actuaire. À faire valider par un expert-comptable avant inscription au bilan.</span>
          </div>

          {data.effectif === 0 ? (
            <Card className="p-10 text-center text-muted"><Icon name="group_off" className="text-[40px] text-outline-variant" /><p className="mt-2">Aucun salarié actif.</p></Card>
          ) : (
            <Card className="p-0 overflow-hidden">
              <div className="p-5 border-b border-border flex items-center gap-2"><Icon name="account_balance_wallet" className="text-muted" /><h3 className="text-subtitle-md font-bold text-ink">Détail par salarié — exercice {data.annee}</h3></div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-body-sm">
                  <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wide">
                    <th className="py-3 px-5">Salarié</th><th className="py-3 px-3 text-right">Ancienneté</th>
                    <th className="py-3 px-3 text-right">Jours CP</th><th className="py-3 px-3 text-right">Provision congés</th>
                    <th className="py-3 px-4 text-right">Engagement IFC</th>
                  </tr></thead>
                  <tbody className="divide-y divide-border text-ink">
                    {data.lignes.map((l, i) => (
                      <tr key={i} className="hover:bg-primary-fixed/10">
                        <td className="py-3 px-5"><span className="font-bold">{l.nom}</span> <span className="text-muted font-mono text-label-md">{l.matricule}</span></td>
                        <td className="py-3 px-3 text-right tabular-nums text-muted">{l.anciennete_ans} ans</td>
                        <td className="py-3 px-3 text-right tabular-nums text-muted">{l.jours_cp}</td>
                        <td className="py-3 px-3 text-right tabular-nums font-semibold">{fcfa(l.provision_conges)}</td>
                        <td className="py-3 px-4 text-right tabular-nums font-semibold">{fcfa(l.engagement_ifc)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot><tr className="bg-primary/5 border-t-2 border-primary font-extrabold text-ink">
                    <td className="py-3 px-5" colSpan={3}>TOTAUX ({data.effectif})</td>
                    <td className="py-3 px-3 text-right tabular-nums">{fcfa(data.total_provision_conges)}</td>
                    <td className="py-3 px-4 text-right tabular-nums">{fcfa(data.total_engagement_ifc)}</td>
                  </tr></tfoot>
                </table>
              </div>
            </Card>
          )}
        </>
      ) : null}
    </div>
  )
}
