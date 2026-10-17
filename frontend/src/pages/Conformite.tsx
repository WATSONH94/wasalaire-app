import { useEffect, useMemo, useState } from 'react'
import { api, ApiError, type Company, type RegulatoryRates } from '../api'
import { Badge, Card, Icon } from '../stitch'

/** Prochaine occurrence d'une échéance mensuelle au jour `day` (ex. ITS/VPS le 10). */
function prochaineEcheance(day: number): Date {
  const now = new Date()
  const d = new Date(now.getFullYear(), now.getMonth(), day)
  if (d < now) d.setMonth(d.getMonth() + 1)
  return d
}
const fmtDate = (d: Date) => d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
const jours = (d: Date) => Math.ceil((d.getTime() - Date.now()) / 86400000)
const pct = (v: number | undefined) => v == null ? '—' : `${(v * 100).toLocaleString('fr-FR', { maximumFractionDigits: 2 })} %`

export default function Conformite() {
  const [companies, setCompanies] = useState<Company[] | null>(null)
  const [rates, setRates] = useState<RegulatoryRates | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const at = new Date().toISOString().slice(0, 10)
    api.companies().then((r) => setCompanies(r.companies)).catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
    api.regulatoryRates(at).then(setRates).catch(() => undefined)
  }, [])

  const its = prochaineEcheance(10)   // DGI ITS/VPS : le 10 du mois suivant
  const cnss = prochaineEcheance(15)  // CNSS : J+15
  const amo = new Date(2026, 9, 29)   // AMO : échéance d'affiliation 29/10/2026 (Décret 2025-672)

  // Registre : une société est « en règle » administrativement si son IFU est renseigné.
  const conformes = useMemo(() => (companies ?? []).filter((c) => c.ifu && c.ifu.trim()).length, [companies])
  const total = companies?.length ?? 0
  const prochaine = [its, cnss].sort((a, b) => a.getTime() - b.getTime())[0]

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Conformité &amp; Registre légal</h2>
          <Badge tone="secondary" icon="verified_user">République du Bénin</Badge>
        </div>
        <p className="text-body-md text-muted mt-1 max-w-2xl">
          Suivi des obligations réglementaires : Code du Travail béninois, DGI (ITS/VPS), CNSS et AMO. Dates et barèmes issus des textes en vigueur.
        </p>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {/* KPIs réels */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5">
          <div className="flex items-center justify-between"><span className="text-label-md text-muted">Sociétés avec IFU renseigné</span><Icon name="domain" className="text-muted" /></div>
          <div className="text-headline-sm font-extrabold text-ink mt-2">{companies == null ? '—' : `${conformes} / ${total}`}</div>
          <div className="text-label-md text-muted mt-1">Identifiant Fiscal Unique (DGI)</div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between"><span className="text-label-md text-muted">Prochaine échéance</span><Badge tone={jours(prochaine) <= 7 ? 'warning' : 'neutral'}>J-{jours(prochaine)}</Badge></div>
          <div className="text-headline-sm font-extrabold text-ink mt-2 capitalize">{fmtDate(prochaine)}</div>
          <div className="text-label-md text-muted mt-1">{prochaine === its ? 'Déclaration DGI ITS/VPS' : 'Cotisations CNSS'}</div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between"><span className="text-label-md text-muted">AMO — affiliation</span><Icon name="health_and_safety" className="text-muted" /></div>
          <div className="text-headline-sm font-extrabold text-ink mt-2 capitalize">{fmtDate(amo)}</div>
          <div className="text-label-md text-muted mt-1">Décret 2025-672 (secteur privé)</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Calendrier réglementaire */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-9 h-9 rounded-xl bg-warning/10 text-warning flex items-center justify-center"><Icon name="event" /></div>
            <div><h3 className="text-subtitle-md font-bold text-ink">Calendrier réglementaire</h3><span className="text-label-md text-muted">Échéances récurrentes Bénin</span></div>
          </div>
          <div className="flex flex-col gap-3">
            {[
              { t: 'Déclaration ITS / VPS — DGI', d: its, s: 'e-Services impots.bj · le 10 du mois suivant', ic: 'gavel' },
              { t: 'Cotisations CNSS', d: cnss, s: 'Mensuel ≥ 20 salariés · J+15', ic: 'verified' },
              { t: 'Affiliation AMO (unique)', d: amo, s: 'Décret 2025-672 · amende 200 000 F/salarié', ic: 'health_and_safety' },
            ].map((e, i) => (
              <div key={i} className="flex items-center justify-between p-3 rounded-xl border border-border">
                <div className="flex items-center gap-3">
                  <Icon name={e.ic} className="text-muted" />
                  <div><div className="font-bold text-ink">{e.t}</div><div className="text-label-md text-muted">{e.s}</div></div>
                </div>
                <div className="text-right shrink-0">
                  <div className="font-bold text-ink capitalize">{fmtDate(e.d)}</div>
                  <Badge tone={jours(e.d) <= 7 ? 'warning' : 'neutral'}>J-{jours(e.d)}</Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Barèmes en vigueur (moteur) */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-9 h-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center"><Icon name="rule" /></div>
            <div><h3 className="text-subtitle-md font-bold text-ink">Barèmes &amp; taux en vigueur</h3><span className="text-label-md text-muted">Appliqués par le moteur de paie</span></div>
          </div>
          <div className="flex flex-col">
            {[
              { l: 'CNSS pension — part salariale', v: pct(rates?.rates.taux_pension_sal), src: 'Loi 98-019 Art. 24-25' },
              { l: 'CNSS pension — part employeur', v: pct(rates?.rates.taux_pension_emp), src: 'Loi 98-019' },
              { l: 'CNSS prestations familiales', v: pct(rates?.rates.taux_pf), src: 'CNSS officiel' },
              { l: 'Versement Patronal (VPS)', v: pct(rates?.rates.taux_vps), src: 'CGI Art. 191-195' },
              { l: 'Barème ITS', v: '5 tranches · 0–30 %', src: 'CGI Art. 125' },
              { l: 'Plafond d’assiette CNSS', v: 'Aucun plafond', src: 'Loi 98-019 Art. 22' },
            ].map((r, i) => (
              <div key={i} className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
                <div><div className="text-body-md text-ink font-semibold">{r.l}</div><div className="text-label-md text-muted">{r.src}</div></div>
                <span className="tabular-nums font-bold text-primary">{r.v}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Registre des sociétés */}
      <Card className="p-0 overflow-hidden">
        <div className="p-5 border-b border-border flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-secondary/10 text-secondary flex items-center justify-center"><Icon name="fact_check" /></div>
          <div><h3 className="text-subtitle-md font-bold text-ink">Registre des sociétés</h3><span className="text-label-md text-muted">Immatriculation fiscale (IFU) par société</span></div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wider">
              <th className="py-3 px-5">Société</th><th className="py-3 px-4">IFU (DGI)</th><th className="py-3 px-4 text-center">Statut</th>
            </tr></thead>
            <tbody className="divide-y divide-border text-body-md text-ink">
              {(companies ?? []).map((c) => (
                <tr key={c.id} className="hover:bg-primary-fixed/10">
                  <td className="py-3 px-5 font-bold">{c.raison_sociale ?? c.nom}</td>
                  <td className="py-3 px-4 font-mono text-muted">{c.ifu || '—'}</td>
                  <td className="py-3 px-4 text-center">
                    {c.ifu && c.ifu.trim()
                      ? <Badge tone="success" icon="check_circle">Renseigné</Badge>
                      : <Badge tone="warning" icon="warning">IFU manquant</Badge>}
                  </td>
                </tr>
              ))}
              {companies != null && companies.length === 0 && (
                <tr><td colSpan={3} className="py-8 text-center text-muted">Aucune société.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="p-4 text-label-md text-muted flex items-start gap-1.5">
          <Icon name="info" className="text-[16px] mt-0.5" />
          Dates et taux issus des textes béninois en vigueur. Le dépôt officiel (DGI, CNSS, AMO) reste une démarche externe.
        </p>
      </Card>
    </div>
  )
}
