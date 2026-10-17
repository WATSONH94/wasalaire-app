import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Payslip } from '../api'
import { Icon } from '../stitch'

const MOIS = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

function Kpi({ label, value, unit, icon, foot, dark }: { label: string; value: string; unit?: string; icon: string; foot?: React.ReactNode; dark?: boolean }) {
  return (
    <div className={`rounded-2xl p-5 border shadow-sm flex flex-col gap-3 ${dark ? 'bg-primary-container text-surface-container-lowest border-border/10' : 'bg-surface border-border'}`}>
      <div className="flex items-start justify-between">
        <span className={`text-label-md font-semibold ${dark ? 'text-on-primary-container' : 'text-muted'}`}>{label}</span>
        <span className={`w-9 h-9 rounded-xl flex items-center justify-center ${dark ? 'bg-surface-container-lowest/10 text-secondary-fixed' : 'bg-surface-container text-primary'}`}><Icon name={icon} className="text-[20px]" /></span>
      </div>
      <div className={`text-[28px] font-extrabold tabular-nums leading-none ${dark ? 'text-surface-container-lowest' : 'text-primary'}`}>{value} {unit && <span className="text-sm font-semibold text-muted">{unit}</span>}</div>
      {foot && <div className={`text-label-md ${dark ? 'text-on-primary-container' : 'text-muted'}`}>{foot}</div>}
    </div>
  )
}

function Ind({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="p-4 rounded-xl bg-surface-container-low/60 border border-border">
      <span className="text-label-md text-muted block">{label}</span>
      <span className="text-subtitle-lg font-extrabold text-ink tabular-nums">{value}</span>
      <span className="text-[11px] text-muted block mt-0.5">{sub}</span>
    </div>
  )
}

export default function Reporting() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [data, setData] = useState<Record<string, number> | null>(null)
  const [slips, setSlips] = useState<Payslip[] | null>(null)
  const [periode, setPeriode] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.reporting(cid).then(setData).catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
    api.companyRuns(cid).then(async (r) => {
      const run = r.runs.find((x) => x.statut === 'cloturee') ?? r.runs[0]
      if (run) { setPeriode(`${MOIS[run.mois]} ${run.annee}`); const p = await api.payslips(run.run_id); setSlips(p.bulletins) }
      else setSlips([])
    }).catch(() => setSlips([]))
  }, [cid])

  const masse = data?.masse_brute ?? 0
  const charges = data?.charges_patronales ?? 0
  const cout = data?.cout_employeur ?? 0
  const net = data?.net_total ?? 0
  const eff = data?.effectif ?? 0
  const moyen = eff ? masse / eff : 0
  const tauxCharges = masse ? (charges / masse) * 100 : 0
  const hasData = !!data && masse > 0

  /** Exporte le rapport (synthèse + ventilation par salarié) en CSV (séparateur « ; », tableurs FR). */
  function exportReport() {
    const n = (v: number) => String(Math.round(v))
    const lignes: string[][] = [
      ['# Rapport RH & masse salariale', periode],
      [],
      ['Indicateur', 'Valeur (FCFA)'],
      ['Masse salariale brute', n(masse)],
      ['Charges patronales (CNSS employeur + VPS)', n(charges)],
      ['Coût employeur total', n(cout)],
      ['Net total versé', n(net)],
      ['Effectif actif', String(eff)],
      ['Salaire brut moyen', n(moyen)],
      ['Taux de charges patronales (%)', tauxCharges.toFixed(1)],
      [],
      ['Salarié', 'Brut', 'Net versé', 'Coût global'],
      ...(slips ?? []).map((p) => [p.nom, n(p.brut), n(p.net), n(p.cout_employeur)]),
    ]
    const csv = lignes.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(';')).join('\r\n')
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url; a.download = `rapport-rh-${periode.replace(/\s+/g, '-').toLowerCase()}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      {/* En-tête */}
      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-headline-lg font-headline-lg text-ink font-extrabold tracking-tight">Reporting &amp; Analyse RH</h1>
            {periode && <span className="inline-flex items-center gap-1.5 bg-surface-container text-ink px-3 py-1 rounded-full text-label-md font-semibold"><span className="w-2 h-2 rounded-full bg-secondary"></span>Période {periode}</span>}
          </div>
          <p className="text-body-md text-muted mt-1 max-w-2xl">Synthèse de la masse salariale, répartition par salarié et indicateurs sociaux conformes aux normes béninoises.</p>
        </div>
        <button onClick={exportReport} disabled={!hasData} className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container shadow-sm shrink-0 disabled:opacity-50"><Icon name="download" className="text-base" />Exporter le rapport</button>
      </div>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {!hasData && data && (
        <div className="p-6 rounded-2xl bg-surface border border-border text-center text-muted">Aucune donnée : lancez et clôturez un cycle de paie pour alimenter le reporting.</div>
      )}

      {hasData && (
        <>
          {/* 4 KPI */}
          <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
            <Kpi label="Masse salariale brute" value={fcfa(masse).replace(' FCFA', '')} unit="FCFA" icon="account_balance_wallet" foot="Base cotisable CNSS & ITS" />
            <Kpi label="Charges patronales" value={fcfa(charges).replace(' FCFA', '')} unit="FCFA" icon="receipt_long" foot="CNSS employeur + VPS" />
            <Kpi label="Coût employeur total" value={fcfa(cout).replace(' FCFA', '')} unit="FCFA" icon="savings" foot="Masse brute + charges" dark />
            <Kpi label="Effectif actif" value={String(eff)} unit="collab." icon="badge" foot="Déclarés DGI / CNSS" />
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Indicateurs RH */}
            <div className="bg-surface rounded-2xl border border-border shadow-sm p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-subtitle-lg font-subtitle-lg text-ink font-bold">Indicateurs RH &amp; Sociaux</h2>
                <span className="inline-flex items-center gap-1 text-label-md text-success font-bold bg-success/10 px-2.5 py-1 rounded-full"><Icon name="verified" className="text-sm" />Normes DGI &amp; DGT Bénin</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Ind label="Effectif total" value={`${eff} salarié${eff > 1 ? 's' : ''}`} sub="Déclarés" />
                <Ind label="Salaire brut moyen" value={fcfa(moyen).replace(' FCFA', '')} sub="FCFA / salarié" />
                <Ind label="Taux charges patronales" value={`${tauxCharges.toFixed(1)} %`} sub="du brut (VPS + CNSS)" />
                <Ind label="Net total versé" value={fcfa(net).replace(' FCFA', '')} sub="FCFA" />
              </div>
              <div className="mt-4 p-4 rounded-xl bg-secondary-fixed/15 border border-secondary/20 flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-secondary/10 text-secondary flex items-center justify-center"><Icon name="shield" /></div>
                <div><div className="text-label-lg font-bold text-ink">Conformité SMIG Bénin</div><div className="text-label-md text-muted">Seuil national : 52 000 FCFA/mois — appliqué par le moteur.</div></div>
              </div>
            </div>

            {/* Ventilation par salarié */}
            <div className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden">
              <div className="p-5 border-b border-border"><h2 className="text-subtitle-lg font-subtitle-lg text-ink font-bold">Ventilation par salarié</h2><p className="text-label-md text-muted">Répartition fiscale et coût global de la période.</p></div>
              {slips == null ? <div className="p-6 flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
                : slips.length === 0 ? <div className="p-8 text-center text-muted">Aucun bulletin sur la période.</div> : (
                  <div className="overflow-x-auto"><table className="w-full text-left border-collapse text-body-md">
                    <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted">
                      <th className="py-2.5 px-4">Salarié</th><th className="py-2.5 px-3 text-right">Brut</th><th className="py-2.5 px-3 text-right">Net versé</th><th className="py-2.5 px-4 text-right">Coût global</th></tr></thead>
                    <tbody className="divide-y divide-border text-ink">
                      {slips.map((p, i) => (
                        <tr key={i} className="hover:bg-primary-fixed/20">
                          <td className="py-2.5 px-4 font-bold">{p.nom}</td>
                          <td className="py-2.5 px-3 text-right tabular-nums text-muted">{fcfa(p.brut)}</td>
                          <td className="py-2.5 px-3 text-right tabular-nums font-bold text-secondary">{fcfa(p.net)}</td>
                          <td className="py-2.5 px-4 text-right tabular-nums text-ink">{fcfa(p.cout_employeur)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table></div>
                )}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
