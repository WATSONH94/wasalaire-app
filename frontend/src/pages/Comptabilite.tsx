import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type AccountingEntry, type Run } from '../api'
import { Badge, Card, Icon } from '../stitch'

const MOIS = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

/** Télécharge le journal au format CSV (séparateur « ; », compatible tableurs FR). */
function exportCsv(entry: AccountingEntry, label: string) {
  const header = ['N° Compte', 'Libellé SYSCOHADA', 'Débit (FCFA)', 'Crédit (FCFA)']
  const rows = entry.lignes.map((l) => [l.compte, l.libelle, String(Math.round(l.debit) || ''), String(Math.round(l.credit) || '')])
  rows.push(['', 'TOTAUX', String(Math.round(entry.total_debit)), String(Math.round(entry.total_credit))])
  const csv = [header, ...rows].map((r) => r.map((c) => `"${c.replace(/"/g, '""')}"`).join(';')).join('\r\n')
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a'); a.href = url; a.download = `journal-paie-${label}.csv`; a.click()
  URL.revokeObjectURL(url)
}

export default function Comptabilite() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [sel, setSel] = useState<Run | null>(null)
  const [entry, setEntry] = useState<AccountingEntry | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.companyRuns(cid)
      .then((r) => {
        const actifs = r.runs.filter((x) => x.actif !== false)
        setRuns(actifs)
        const first = actifs.find((x) => x.statut === 'cloturee') ?? null
        if (first) setSel(first)
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
  }, [cid])

  useEffect(() => {
    if (!sel) { setEntry(null); return }
    if (sel.statut !== 'cloturee') { setEntry(null); return }
    setLoading(true); setEntry(null); setError(null)
    // L'écriture SYSCOHADA est générée (idempotente) à la clôture : POST renvoie l'existante.
    api.accounting(sel.run_id)
      .then(setEntry)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
      .finally(() => setLoading(false))
  }, [sel])

  const periode = sel ? `${MOIS[sel.mois]} ${sel.annee}` : ''
  const piece = sel ? `OD-PAIE-${sel.annee}-${String(sel.mois).padStart(2, '0')}` : ''

  return (
    <div className="flex flex-col gap-5">
      {/* En-tête */}
      <Card className="p-6">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Comptabilité &amp; Écritures de Paie</h2>
              {sel?.statut === 'cloturee' && <Badge tone="success" icon="check_circle">Cycle {periode} clôturé</Badge>}
            </div>
            <p className="text-body-md text-muted mt-1 max-w-2xl">
              Génération automatique des écritures du journal d'opérations diverses (OD) de paie selon le plan comptable <span className="font-semibold text-ink">SYSCOHADA Révisé</span>.
            </p>
          </div>
          <button
            onClick={() => entry && sel && exportCsv(entry, `${sel.annee}-${String(sel.mois).padStart(2, '0')}`)}
            disabled={!entry}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container transition-colors shadow-sm disabled:opacity-50 shrink-0">
            <Icon name="download" className="text-[18px]" /> Exporter (CSV)
          </button>
        </div>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {runs == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : runs.filter((r) => r.statut === 'cloturee').length === 0 ? (
        <Card className="p-10 text-center">
          <Icon name="account_balance" className="text-[40px] text-outline-variant" />
          <p className="text-muted mt-2">Aucun cycle clôturé. L'écriture comptable est générée une fois la paie validée et clôturée.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Cycles clôturés */}
          <Card className="p-3 lg:col-span-1 h-fit">
            <div className="text-label-md font-bold text-muted uppercase px-2 py-1">Cycles clôturés</div>
            <div className="flex flex-col gap-1">
              {runs.filter((r) => r.statut === 'cloturee').map((r) => (
                <button key={r.run_id} onClick={() => setSel(r)}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-colors ${
                    sel?.run_id === r.run_id ? 'bg-secondary/10 text-secondary' : 'hover:bg-surface-container-low text-ink'}`}>
                  <span className="font-bold capitalize">{MOIS[r.mois]} {r.annee}</span>
                  <Icon name="chevron_right" className="text-muted" />
                </button>
              ))}
            </div>
          </Card>

          {/* Détail */}
          <div className="lg:col-span-2 flex flex-col gap-5">
            {loading ? (
              <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Génération de l'écriture…</div>
            ) : entry ? (
              <>
                {/* KPIs */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <Card className="p-5">
                    <div className="flex items-center justify-between"><span className="text-label-md text-muted">Total Débit</span><Icon name="trending_up" className="text-muted" /></div>
                    <div className="text-headline-sm font-extrabold text-ink tabular-nums mt-2">{fcfa(entry.total_debit)}</div>
                    <div className="text-label-md text-muted mt-1">Comptes classe 6 (Charges)</div>
                  </Card>
                  <Card className="p-5">
                    <div className="flex items-center justify-between"><span className="text-label-md text-muted">Total Crédit</span><Icon name="trending_down" className="text-muted" /></div>
                    <div className="text-headline-sm font-extrabold text-ink tabular-nums mt-2">{fcfa(entry.total_credit)}</div>
                    <div className="text-label-md text-muted mt-1">Comptes classe 4 (Tiers &amp; État)</div>
                  </Card>
                  <Card className="p-5">
                    <span className="text-label-md text-muted">Statut de Balance</span>
                    {entry.total_debit === entry.total_credit ? (
                      <div className="mt-2 inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-success text-white font-bold w-full justify-center">
                        <Icon name="check_circle" className="text-[18px]" /> Débit = Crédit (Équilibré)
                      </div>
                    ) : (
                      <div className="mt-2 inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-danger text-white font-bold w-full justify-center">
                        <Icon name="error" className="text-[18px]" /> Déséquilibre
                      </div>
                    )}
                    <div className="text-label-md text-muted mt-1 text-center">Écart : {fcfa(Math.abs(entry.total_debit - entry.total_credit))}</div>
                  </Card>
                </div>

                {/* Journal */}
                <Card className="p-0 overflow-hidden">
                  <div className="p-5 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center"><Icon name="menu_book" /></div>
                      <div>
                        <h3 className="text-subtitle-md font-bold text-ink">Journal d'OD de Paie — SYSCOHADA</h3>
                        <span className="text-label-md text-muted">Pièce N° <span className="font-mono font-semibold text-primary">{piece}</span> · {periode}</span>
                      </div>
                    </div>
                    <Badge tone="success" icon="verified">Validé</Badge>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wider">
                        <th className="py-3 px-5">N° Compte</th><th className="py-3 px-4">Libellé SYSCOHADA</th>
                        <th className="py-3 px-4 text-right">Débit</th><th className="py-3 px-4 text-right">Crédit</th>
                      </tr></thead>
                      <tbody className="divide-y divide-border text-body-md text-ink">
                        {entry.lignes.filter((l) => l.debit || l.credit).map((l, i) => (
                          <tr key={i} className="hover:bg-primary-fixed/10">
                            <td className="py-3 px-5 font-mono font-bold text-primary">{l.compte}</td>
                            <td className="py-3 px-4">{l.libelle}</td>
                            <td className="py-3 px-4 text-right tabular-nums font-semibold">{l.debit ? fcfa(l.debit) : '—'}</td>
                            <td className="py-3 px-4 text-right tabular-nums font-semibold">{l.credit ? fcfa(l.credit) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot><tr className="bg-primary/5 border-t-2 border-primary font-extrabold text-ink">
                        <td className="py-3 px-5" colSpan={2}>TOTAUX</td>
                        <td className="py-3 px-4 text-right tabular-nums">{fcfa(entry.total_debit)}</td>
                        <td className="py-3 px-4 text-right tabular-nums">{fcfa(entry.total_credit)}</td>
                      </tr></tfoot>
                    </table>
                  </div>
                  <p className="p-4 text-label-md text-muted flex items-start gap-1.5">
                    <Icon name="info" className="text-[16px] mt-0.5" />
                    Écriture consolidée équilibrée (débit = crédit). Comptes SYSCOHADA Révisé : 66/64 charges, 43 CNSS, 447 ITS, 442 VPS, 422 net dû.
                  </p>
                </Card>
              </>
            ) : (
              <Card className="p-8 text-center text-muted">Sélectionnez un cycle clôturé pour voir son écriture comptable.</Card>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
