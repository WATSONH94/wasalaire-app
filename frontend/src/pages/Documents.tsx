import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Attestation, type Employee, type Registres, type Run } from '../api'
import { Badge, Card, Icon } from '../stitch'

const MOIS = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

type Onglet = 'livre' | 'cnss' | 'dgi' | 'attestations'
type TypeAttest = 'travail' | 'salaire' | 'virement'

/** Télécharge un tableau au format CSV (séparateur « ; », compatible tableurs FR, BOM UTF-8). */
function csv(filename: string, rows: (string | number)[][]) {
  const body = rows.map((r) => r.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(';')).join('\r\n')
  const url = URL.createObjectURL(new Blob(['﻿' + body], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export default function Documents() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [sel, setSel] = useState<Run | null>(null)
  const [reg, setReg] = useState<Registres | null>(null)
  const [onglet, setOnglet] = useState<Onglet>('livre')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  // Attestations (par salarié, indépendant du cycle)
  const [emps, setEmps] = useState<Employee[] | null>(null)
  const [selEmp, setSelEmp] = useState<Employee | null>(null)
  const [attType, setAttType] = useState<TypeAttest>('travail')
  const [att, setAtt] = useState<Attestation | null>(null)
  const [attLoading, setAttLoading] = useState(false)

  useEffect(() => {
    api.companyRuns(cid)
      .then((r) => {
        const actifs = r.runs.filter((x) => x.actif !== false)
        setRuns(actifs)
        const first = actifs.find((x) => x.statut === 'cloturee') ?? actifs[0] ?? null
        if (first) setSel(first)
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
    api.employees(cid).then((r) => setEmps(r.employes)).catch(() => setEmps([]))
  }, [cid])

  useEffect(() => {
    if (!sel) { setReg(null); return }
    setLoading(true); setReg(null); setError(null)
    api.registres(sel.run_id)
      .then(setReg)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
      .finally(() => setLoading(false))
  }, [sel])

  // Charge l'attestation dès qu'un salarié + type sont choisis.
  useEffect(() => {
    if (onglet !== 'attestations' || !selEmp) { setAtt(null); return }
    setAttLoading(true); setAtt(null); setError(null)
    api.attestation(selEmp.id, cid, attType)
      .then(setAtt)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
      .finally(() => setAttLoading(false))
  }, [onglet, selEmp, attType, cid])

  const periode = reg ? `${MOIS[reg.periode.mois]} ${reg.periode.annee}` : ''
  const suffixe = reg ? `${reg.periode.annee}-${String(reg.periode.mois).padStart(2, '0')}` : ''
  const vide = reg != null && reg.effectif === 0
  const isAttest = onglet === 'attestations'

  const ongletsDef: { key: Onglet; label: string; icon: string }[] = [
    { key: 'livre', label: 'Livre de paie', icon: 'menu_book' },
    { key: 'cnss', label: 'Bordereau CNSS', icon: 'health_and_safety' },
    { key: 'dgi', label: 'Bordereau DGI (ITS/VPS)', icon: 'gavel' },
    { key: 'attestations', label: 'Attestations', icon: 'badge' },
  ]
  const typesAttest: { key: TypeAttest; label: string }[] = [
    { key: 'travail', label: 'De travail' },
    { key: 'salaire', label: 'De salaire' },
    { key: 'virement', label: 'De virement' },
  ]

  function exporter() {
    if (!reg) return
    if (onglet === 'livre') {
      const t = reg.livre_paie.totaux
      csv(`livre-de-paie-${suffixe}.csv`, [
        ['# Livre de paie', periode, reg.societe.raison_sociale ?? ''],
        ['Matricule', 'Nom', 'Brut', 'Assiette CNSS', 'CNSS salariale', 'CNSS patronale', 'Base ITS', 'ITS', 'VPS', 'ORTB', 'Net à payer', 'Coût employeur'],
        ...reg.livre_paie.lignes.map((l) => [l.matricule, l.nom, l.brut, l.assiette_cnss, l.cnss_sal, l.cnss_pat, l.base_its, l.its, l.vps, l.ortb, l.net_a_payer, l.cout_employeur]),
        ['', 'TOTAUX', t.brut, t.assiette_cnss, t.cnss_sal, t.cnss_pat, t.base_its, t.its, t.vps, t.ortb, t.net_a_payer, t.cout_employeur],
      ])
    } else if (onglet === 'cnss') {
      const b = reg.bordereau_cnss
      csv(`bordereau-cnss-${suffixe}.csv`, [
        ['# Bordereau CNSS (liste nominative)', periode, reg.societe.raison_sociale ?? ''],
        ['N° employeur CNSS', reg.societe.num_employeur_cnss ?? ''],
        ['N° assurance', 'Nom', 'Salaire brut (assiette)', 'Part salariale (3,6%)', 'Part patronale'],
        ...b.lignes.map((l) => [l.num_cnss, l.nom, l.assiette, l.part_sal, l.part_pat]),
        ['', 'TOTAUX', b.assiette_totale, b.total_sal, b.total_pat],
        ['', 'TOTAL À REVERSER CNSS', '', '', b.total],
      ])
    } else if (onglet === 'dgi') {
      const b = reg.bordereau_dgi
      csv(`bordereau-dgi-${suffixe}.csv`, [
        ['# Bordereau DGI — ITS/VPS', periode, reg.societe.raison_sociale ?? ''],
        ['IFU', reg.societe.ifu ?? ''],
        ['Matricule', 'Nom', 'Base ITS', 'ITS', 'VPS'],
        ...b.lignes.map((l) => [l.matricule, l.nom, l.base_its, l.its, l.vps]),
        ['', 'TOTAUX', b.base_its_totale, b.its_total, b.vps_total],
        ['', 'TOTAL À REVERSER DGI (ITS+VPS)', '', '', b.total_a_reverser],
      ])
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6 print:hidden">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Documents &amp; Registres légaux</h2>
              {!isAttest && reg && <Badge tone={reg.periode.statut === 'cloturee' ? 'success' : 'neutral'} icon={reg.periode.statut === 'cloturee' ? 'check_circle' : 'sync'}>{reg.periode.statut === 'cloturee' ? `Cycle ${periode} clôturé` : `Cycle ${periode}`}</Badge>}
            </div>
            <p className="text-body-md text-muted mt-1 max-w-2xl">
              Livre de paie, bordereaux CNSS &amp; DGI et attestations RH, assemblés depuis les données réelles — <span className="font-semibold text-ink">valeurs du moteur, sans recalcul ni champ inventé</span>.
            </p>
          </div>
          {!isAttest && (
            <div className="flex items-center gap-2 shrink-0">
              <button onClick={() => window.print()} disabled={!reg || vide} className="inline-flex items-center gap-2 px-4 py-2.5 bg-secondary-fixed text-ink font-bold rounded-xl hover:bg-secondary-fixed-dim transition-colors disabled:opacity-50"><Icon name="print" className="text-[18px]" /> Imprimer</button>
              <button onClick={exporter} disabled={!reg || vide} className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container transition-colors shadow-sm disabled:opacity-50"><Icon name="download" className="text-[18px]" /> Exporter (CSV)</button>
            </div>
          )}
        </div>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold print:hidden">{error}</div>}

      {/* Onglets */}
      <div className="flex items-center gap-1 bg-surface-container-low p-1 rounded-xl border border-border w-fit print:hidden flex-wrap">
        {ongletsDef.map((o) => (
          <button key={o.key} onClick={() => setOnglet(o.key)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-label-lg font-bold transition-colors ${
              onglet === o.key ? 'bg-surface text-primary shadow-sm' : 'text-muted hover:text-ink'}`}>
            <Icon name={o.icon} className="text-[18px]" /> {o.label}
          </button>
        ))}
      </div>

      {isAttest ? (
        /* ─────────── Attestations (par salarié) ─────────── */
        emps == null ? (
          <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
        ) : emps.length === 0 ? (
          <Card className="p-10 text-center"><Icon name="badge" className="text-[40px] text-outline-variant" /><p className="text-muted mt-2">Aucun salarié. Ajoutez un salarié pour générer ses attestations.</p></Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
            <Card className="p-3 lg:col-span-1 h-fit print:hidden">
              <div className="text-label-md font-bold text-muted uppercase px-2 py-1">Salariés</div>
              <div className="flex flex-col gap-1">
                {emps.map((e) => (
                  <button key={e.id} onClick={() => setSelEmp(e)}
                    className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-colors ${
                      selEmp?.id === e.id ? 'bg-secondary/10 text-secondary' : 'hover:bg-surface-container-low text-ink'}`}>
                    <span className="font-bold">{e.nom}</span>
                    <span className="text-label-md text-muted font-mono">{e.matricule}</span>
                  </button>
                ))}
              </div>
            </Card>
            <div className="lg:col-span-3 flex flex-col gap-4">
              {!selEmp ? (
                <Card className="p-8 text-center text-muted">Sélectionnez un salarié pour générer une attestation.</Card>
              ) : (
                <>
                  <div className="flex items-center justify-between gap-3 flex-wrap print:hidden">
                    <div className="flex items-center gap-1 bg-surface-container-low p-1 rounded-xl border border-border w-fit">
                      {typesAttest.map((t) => (
                        <button key={t.key} onClick={() => setAttType(t.key)}
                          className={`px-3 py-1.5 rounded-lg text-label-md font-bold transition-colors ${attType === t.key ? 'bg-surface text-primary shadow-sm' : 'text-muted hover:text-ink'}`}>
                          {t.label}
                        </button>
                      ))}
                    </div>
                    <button onClick={() => window.print()} disabled={!att} className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container transition-colors shadow-sm disabled:opacity-50"><Icon name="print" className="text-[18px]" /> Imprimer</button>
                  </div>
                  {attLoading ? (
                    <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Génération…</div>
                  ) : att ? (
                    <Card className="p-8">
                      <pre className="whitespace-pre-wrap font-body-md text-body-md text-ink leading-relaxed" style={{ fontFamily: 'inherit' }}>{att.contenu}</pre>
                    </Card>
                  ) : (
                    <Card className="p-8 text-center text-muted">—</Card>
                  )}
                  <p className="text-label-md text-muted flex items-start gap-1.5 print:hidden">
                    <Icon name="info" className="text-[16px] mt-0.5" />
                    Attestation générée depuis les données réelles du dossier (aucun champ inventé : un élément absent apparaît « — »). À signer par un responsable habilité.
                  </p>
                </>
              )}
            </div>
          </div>
        )
      ) : runs == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : runs.length === 0 ? (
        <Card className="p-10 text-center">
          <Icon name="description" className="text-[40px] text-outline-variant" />
          <p className="text-muted mt-2">Aucun cycle de paie. Les registres sont générés une fois une paie calculée.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
          {/* Cycles */}
          <Card className="p-3 lg:col-span-1 h-fit print:hidden">
            <div className="text-label-md font-bold text-muted uppercase px-2 py-1">Cycles</div>
            <div className="flex flex-col gap-1">
              {runs.map((r) => (
                <button key={r.run_id} onClick={() => setSel(r)}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-colors ${
                    sel?.run_id === r.run_id ? 'bg-secondary/10 text-secondary' : 'hover:bg-surface-container-low text-ink'}`}>
                  <span className="font-bold capitalize">{MOIS[r.mois]} {r.annee}</span>
                  <Badge tone={r.statut === 'cloturee' ? 'success' : 'neutral'}>{r.statut === 'cloturee' ? 'Clôturé' : r.statut}</Badge>
                </button>
              ))}
            </div>
          </Card>

          <div className="lg:col-span-3 flex flex-col gap-5">
            {loading ? (
              <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Assemblage du registre…</div>
            ) : !reg ? (
              <Card className="p-8 text-center text-muted">Sélectionnez un cycle.</Card>
            ) : vide ? (
              <Card className="p-8 text-center text-muted">Ce cycle n'a pas encore de bulletins calculés.</Card>
            ) : (
              <Card className="p-0 overflow-hidden">
                <div className="p-5 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h3 className="text-subtitle-md font-bold text-ink">{reg.societe.raison_sociale}</h3>
                    <span className="text-label-md text-muted">
                      {onglet === 'cnss' ? `N° employeur CNSS : ${reg.societe.num_employeur_cnss || '—'}` : onglet === 'dgi' ? `IFU : ${reg.societe.ifu || '—'}` : `Période de paie`} · <span className="capitalize">{periode}</span> · {reg.effectif} salarié{reg.effectif > 1 ? 's' : ''}
                    </span>
                  </div>
                  <Badge tone="neutral" icon="verified">{onglet === 'livre' ? 'Livre de paie' : onglet === 'cnss' ? 'Liste nominative CNSS' : 'Déclaration ITS/VPS'}</Badge>
                </div>

                <div className="overflow-x-auto">
                  {onglet === 'livre' && (
                    <table className="w-full text-left border-collapse text-body-sm">
                      <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wide">
                        <th className="py-3 px-4">Salarié</th><th className="py-3 px-3 text-right">Brut</th>
                        <th className="py-3 px-3 text-right">CNSS sal.</th><th className="py-3 px-3 text-right">ITS</th>
                        <th className="py-3 px-3 text-right">VPS</th><th className="py-3 px-3 text-right">Net à payer</th>
                        <th className="py-3 px-4 text-right">Coût employeur</th>
                      </tr></thead>
                      <tbody className="divide-y divide-border text-ink">
                        {reg.livre_paie.lignes.map((l, i) => (
                          <tr key={i} className="hover:bg-primary-fixed/10">
                            <td className="py-2.5 px-4"><span className="font-bold">{l.nom}</span> <span className="text-muted font-mono text-label-md">{l.matricule}</span></td>
                            <td className="py-2.5 px-3 text-right tabular-nums">{fcfa(l.brut)}</td>
                            <td className="py-2.5 px-3 text-right tabular-nums text-muted">{fcfa(l.cnss_sal)}</td>
                            <td className="py-2.5 px-3 text-right tabular-nums text-muted">{fcfa(l.its)}</td>
                            <td className="py-2.5 px-3 text-right tabular-nums text-muted">{fcfa(l.vps)}</td>
                            <td className="py-2.5 px-3 text-right tabular-nums font-bold text-secondary">{fcfa(l.net_a_payer)}</td>
                            <td className="py-2.5 px-4 text-right tabular-nums">{fcfa(l.cout_employeur)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot><tr className="bg-primary/5 border-t-2 border-primary font-extrabold text-ink">
                        <td className="py-3 px-4">TOTAUX ({reg.effectif})</td>
                        <td className="py-3 px-3 text-right tabular-nums">{fcfa(reg.livre_paie.totaux.brut)}</td>
                        <td className="py-3 px-3 text-right tabular-nums">{fcfa(reg.livre_paie.totaux.cnss_sal)}</td>
                        <td className="py-3 px-3 text-right tabular-nums">{fcfa(reg.livre_paie.totaux.its)}</td>
                        <td className="py-3 px-3 text-right tabular-nums">{fcfa(reg.livre_paie.totaux.vps)}</td>
                        <td className="py-3 px-3 text-right tabular-nums text-secondary">{fcfa(reg.livre_paie.totaux.net_a_payer)}</td>
                        <td className="py-3 px-4 text-right tabular-nums">{fcfa(reg.livre_paie.totaux.cout_employeur)}</td>
                      </tr></tfoot>
                    </table>
                  )}

                  {onglet === 'cnss' && (
                    <table className="w-full text-left border-collapse text-body-sm">
                      <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wide">
                        <th className="py-3 px-4">N° assurance</th><th className="py-3 px-4">Nom</th>
                        <th className="py-3 px-3 text-right">Salaire brut (assiette)</th>
                        <th className="py-3 px-3 text-right">Part salariale</th><th className="py-3 px-4 text-right">Part patronale</th>
                      </tr></thead>
                      <tbody className="divide-y divide-border text-ink">
                        {reg.bordereau_cnss.lignes.map((l, i) => (
                          <tr key={i} className="hover:bg-primary-fixed/10">
                            <td className="py-2.5 px-4 font-mono text-muted">{l.num_cnss || '—'}</td>
                            <td className="py-2.5 px-4 font-bold">{l.nom}</td>
                            <td className="py-2.5 px-3 text-right tabular-nums">{fcfa(l.assiette)}</td>
                            <td className="py-2.5 px-3 text-right tabular-nums text-muted">{fcfa(l.part_sal)}</td>
                            <td className="py-2.5 px-4 text-right tabular-nums text-muted">{fcfa(l.part_pat)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-primary/5 border-t-2 border-primary font-extrabold text-ink">
                          <td className="py-3 px-4" colSpan={2}>TOTAUX</td>
                          <td className="py-3 px-3 text-right tabular-nums">{fcfa(reg.bordereau_cnss.assiette_totale)}</td>
                          <td className="py-3 px-3 text-right tabular-nums">{fcfa(reg.bordereau_cnss.total_sal)}</td>
                          <td className="py-3 px-4 text-right tabular-nums">{fcfa(reg.bordereau_cnss.total_pat)}</td>
                        </tr>
                        <tr className="bg-secondary/10 font-extrabold text-ink">
                          <td className="py-3 px-4" colSpan={4}>TOTAL À REVERSER CNSS (salariale + patronale)</td>
                          <td className="py-3 px-4 text-right tabular-nums text-secondary">{fcfa(reg.bordereau_cnss.total)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  )}

                  {onglet === 'dgi' && (
                    <table className="w-full text-left border-collapse text-body-sm">
                      <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wide">
                        <th className="py-3 px-4">Salarié</th><th className="py-3 px-3 text-right">Base ITS</th>
                        <th className="py-3 px-3 text-right">ITS</th><th className="py-3 px-4 text-right">VPS</th>
                      </tr></thead>
                      <tbody className="divide-y divide-border text-ink">
                        {reg.bordereau_dgi.lignes.map((l, i) => (
                          <tr key={i} className="hover:bg-primary-fixed/10">
                            <td className="py-2.5 px-4"><span className="font-bold">{l.nom}</span> <span className="text-muted font-mono text-label-md">{l.matricule}</span></td>
                            <td className="py-2.5 px-3 text-right tabular-nums">{fcfa(l.base_its)}</td>
                            <td className="py-2.5 px-3 text-right tabular-nums text-muted">{fcfa(l.its)}</td>
                            <td className="py-2.5 px-4 text-right tabular-nums text-muted">{fcfa(l.vps)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-primary/5 border-t-2 border-primary font-extrabold text-ink">
                          <td className="py-3 px-4">TOTAUX</td>
                          <td className="py-3 px-3 text-right tabular-nums">{fcfa(reg.bordereau_dgi.base_its_totale)}</td>
                          <td className="py-3 px-3 text-right tabular-nums">{fcfa(reg.bordereau_dgi.its_total)}</td>
                          <td className="py-3 px-4 text-right tabular-nums">{fcfa(reg.bordereau_dgi.vps_total)}</td>
                        </tr>
                        <tr className="bg-secondary/10 font-extrabold text-ink">
                          <td className="py-3 px-4" colSpan={3}>TOTAL À REVERSER DGI (ITS + VPS) · échéance le 10</td>
                          <td className="py-3 px-4 text-right tabular-nums text-secondary">{fcfa(reg.bordereau_dgi.total_a_reverser)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  )}
                </div>

                <p className="p-4 text-label-md text-muted flex items-start gap-1.5 print:hidden">
                  <Icon name="info" className="text-[16px] mt-0.5" />
                  Registre assemblé depuis les bulletins calculés par le moteur (aucun recalcul). Le dépôt officiel DGI/CNSS reste une démarche externe.
                </p>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
