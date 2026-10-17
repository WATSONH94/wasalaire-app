import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError, fcfa, type Employee, type RuptureInput, type SoldeToutCompte as STC } from '../api'
import { Badge, Card, Icon } from '../stitch'

const TYPES: { key: RuptureInput['type_rupture']; label: string; hint: string }[] = [
  { key: 'licenciement', label: 'Licenciement', hint: 'Indemnité de licenciement (CCGT Art. 36), abattement fiscal 25 %.' },
  { key: 'demission', label: 'Démission', hint: "Pas d'indemnité de rupture ; solde des congés + préavis éventuel." },
  { key: 'retraite', label: 'Départ à la retraite', hint: 'Indemnité de départ à la retraite (CCGT Art. 57).' },
  { key: 'fin_cdd', label: 'Fin de CDD', hint: 'Indemnité de fin de collaboration (Loi 2017-05 Art. 13).' },
  { key: 'deces', label: 'Décès', hint: 'Capital décès (CCGT Art. 37). ⚠️ Fiscalité de l\'année à confirmer.' },
]

function NumField({ label, value, onChange, hint, suffix }: {
  label: string; value: number; onChange: (v: number) => void; hint?: string; suffix?: string
}) {
  return (
    <label className="block space-y-1">
      <span className="block text-label-md font-semibold text-ink">{label}</span>
      <div className="relative">
        <input type="number" min={0} value={Number.isNaN(value) ? '' : value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="w-full px-3 py-2.5 rounded-xl border border-border bg-white text-ink focus:border-secondary-fixed-dim focus:ring-2 focus:ring-secondary-fixed-dim/30 outline-none tabular-nums" />
        {suffix && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-label-md text-muted">{suffix}</span>}
      </div>
      {hint && <span className="block text-[11px] text-muted">{hint}</span>}
    </label>
  )
}

function LigneMontant({ label, montant, fort, retenue }: { label: string; montant: number; fort?: boolean; retenue?: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">
      <span className="text-body-md text-muted">{label}</span>
      <span className={`tabular-nums ${fort ? 'font-extrabold text-ink' : 'font-semibold'} ${retenue ? 'text-danger' : 'text-ink'}`}>
        {retenue ? '- ' : ''}{fcfa(montant)}
      </span>
    </div>
  )
}

export default function SoldeToutCompte() {
  const { companyId } = useParams()
  const cid = companyId as string
  const [emps, setEmps] = useState<Employee[] | null>(null)
  const [selEmp, setSelEmp] = useState<Employee | null>(null)
  const [input, setInput] = useState<RuptureInput>({
    type_rupture: 'licenciement', anciennete_ans: 1, jours_travailles_dernier_mois: 30,
    jours_conges_acquis_non_pris: 0, preavis_indemnite: 0,
  })
  const [apercu, setApercu] = useState<STC | null>(null)
  const [confirmed, setConfirmed] = useState<STC | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { api.employees(cid).then((r) => setEmps(r.employes)).catch(() => setEmps([])) }, [cid])

  // Réinitialise l'aperçu quand on change de salarié/paramètres.
  useEffect(() => { setApercu(null); setConfirmed(null); setConfirming(false); setError(null) }, [selEmp, input])

  const calculer = () => {
    if (!selEmp) return
    setBusy(true); setError(null); setConfirmed(null); setConfirming(false)
    api.rupture(selEmp.id, cid, input, true)
      .then(setApercu)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
      .finally(() => setBusy(false))
  }

  const confirmer = () => {
    if (!selEmp) return
    setBusy(true); setError(null)
    api.rupture(selEmp.id, cid, input, false)
      .then((r) => { setConfirmed(r); setApercu(null); setConfirming(false) })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
      .finally(() => setBusy(false))
  }

  const res = confirmed ?? apercu
  const typeInfo = TYPES.find((t) => t.key === input.type_rupture)

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Rupture &amp; Solde de tout compte</h2>
          <Badge tone="warning" icon="gavel">Opération sensible</Badge>
        </div>
        <p className="text-body-md text-muted mt-1 max-w-2xl">
          Calcul du solde de tout compte (salaire au prorata, congés non pris, indemnité de rupture, fiscalité).
          <span className="font-semibold text-ink"> L'aperçu ne clôt rien</span> ; la confirmation clôture le contrat.
        </p>
      </Card>

      {error && <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold">{error}</div>}

      {emps == null ? (
        <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>
      ) : emps.length === 0 ? (
        <Card className="p-10 text-center"><Icon name="group_off" className="text-[40px] text-outline-variant" /><p className="text-muted mt-2">Aucun salarié.</p></Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Paramètres */}
          <Card className="p-5 lg:col-span-1 h-fit flex flex-col gap-4">
            <div>
              <span className="block text-label-md font-semibold text-ink mb-1">Salarié</span>
              <select value={selEmp?.id ?? ''} onChange={(e) => setSelEmp(emps.find((x) => x.id === e.target.value) ?? null)}
                className="w-full px-3 py-2.5 rounded-xl border border-border bg-white text-ink outline-none focus:border-secondary-fixed-dim">
                <option value="">— Sélectionner —</option>
                {emps.map((e) => <option key={e.id} value={e.id}>{e.nom} ({e.matricule})</option>)}
              </select>
            </div>
            <div>
              <span className="block text-label-md font-semibold text-ink mb-1">Motif de rupture</span>
              <select value={input.type_rupture} onChange={(e) => setInput({ ...input, type_rupture: e.target.value as RuptureInput['type_rupture'] })}
                className="w-full px-3 py-2.5 rounded-xl border border-border bg-white text-ink outline-none focus:border-secondary-fixed-dim">
                {TYPES.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
              </select>
              {typeInfo && <span className="block text-[11px] text-muted mt-1">{typeInfo.hint}</span>}
            </div>
            <NumField label="Ancienneté" value={input.anciennete_ans} onChange={(v) => setInput({ ...input, anciennete_ans: v })} suffix="ans" />
            <NumField label="Jours travaillés le dernier mois" value={input.jours_travailles_dernier_mois} onChange={(v) => setInput({ ...input, jours_travailles_dernier_mois: v })} suffix="/ 30" />
            <NumField label="Jours de congés acquis non pris" value={input.jours_conges_acquis_non_pris} onChange={(v) => setInput({ ...input, jours_conges_acquis_non_pris: v })} suffix="j" />
            <NumField label="Indemnité compensatrice de préavis" value={input.preavis_indemnite} onChange={(v) => setInput({ ...input, preavis_indemnite: v })} suffix="FCFA" hint="0 si le préavis est effectué." />
            <button onClick={calculer} disabled={!selEmp || busy}
              className="mt-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rounded-xl hover:bg-primary-container transition-colors shadow-sm disabled:opacity-50">
              <Icon name="calculate" className="text-[18px]" /> {busy && !confirming ? 'Calcul…' : "Calculer l'aperçu"}
            </button>
          </Card>

          {/* Résultat */}
          <div className="lg:col-span-2 flex flex-col gap-5">
            {!res ? (
              <Card className="p-10 text-center text-muted">
                <Icon name="receipt_long" className="text-[40px] text-outline-variant" />
                <p className="mt-2">Renseignez les paramètres et calculez l'aperçu du solde de tout compte.</p>
              </Card>
            ) : (
              <>
                {confirmed && (
                  <div className="p-3 rounded-xl bg-success/10 border border-success/30 text-ink text-label-md font-semibold flex items-center gap-2">
                    <Icon name="check_circle" className="text-success" /> Rupture confirmée — le contrat de {selEmp?.nom} est clôturé.
                  </div>
                )}
                <Card className="p-0 overflow-hidden">
                  <div className="p-5 border-b border-border flex items-center justify-between gap-2">
                    <div>
                      <h3 className="text-subtitle-md font-bold text-ink">Solde de tout compte — {selEmp?.nom}</h3>
                      <span className="text-label-md text-muted capitalize">{typeInfo?.label} · {input.anciennete_ans} an(s) d'ancienneté</span>
                    </div>
                    <Badge tone={confirmed ? 'success' : 'neutral'} icon={confirmed ? 'lock' : 'visibility'}>{confirmed ? 'Clôturé' : 'Aperçu'}</Badge>
                  </div>
                  <div className="p-5">
                    <LigneMontant label="Salaire du mois (prorata)" montant={res.salaire_mois_prorata} />
                    <LigneMontant label="Indemnité compensatrice de congés" montant={res.indemnite_conges} />
                    {res.indemnite_preavis > 0 && <LigneMontant label="Indemnité de préavis" montant={res.indemnite_preavis} />}
                    <LigneMontant label={`Indemnité de rupture${res.abattement_rupture ? ` (abattement ${Math.round(res.abattement_rupture * 100)} %)` : ''}`} montant={res.indemnite_rupture} />
                    <LigneMontant label="Total brut" montant={res.total_brut} fort />
                    <LigneMontant label="ITS estimé" montant={res.its_estime} retenue />
                    <div className="flex items-center justify-between py-3 mt-1 border-t-2 border-primary">
                      <span className="font-extrabold text-primary">Net estimé à payer</span>
                      <span className="tabular-nums font-extrabold text-secondary text-subtitle-md">{fcfa(res.net_estime)}</span>
                    </div>
                  </div>
                  <div className="p-4 bg-warm-sand/15 border-t border-border text-label-md text-ink flex items-start gap-2">
                    <Icon name="info" className="text-warning text-[18px] mt-0.5" />
                    <span>Sources : {res.source}</span>
                  </div>
                </Card>

                {/* Confirmation destructive */}
                {!confirmed && (
                  confirming ? (
                    <Card className="p-5 border border-danger/30 bg-danger/5">
                      <div className="flex items-start gap-2 mb-3">
                        <Icon name="warning" className="text-danger text-[20px] mt-0.5" />
                        <p className="text-body-md text-ink font-semibold">
                          Confirmer la rupture <span className="font-extrabold">clôture définitivement le contrat</span> de {selEmp?.nom} (statut « clos »). Cette action est tracée.
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={confirmer} disabled={busy}
                          className="inline-flex items-center gap-2 px-4 py-2.5 bg-danger text-white font-bold rounded-xl hover:opacity-90 disabled:opacity-50">
                          <Icon name="gavel" className="text-[18px]" /> {busy ? 'Clôture…' : 'Oui, clôturer le contrat'}
                        </button>
                        <button onClick={() => setConfirming(false)} disabled={busy}
                          className="px-4 py-2.5 bg-surface-container text-ink font-bold rounded-xl hover:bg-surface-container-high">Annuler</button>
                      </div>
                    </Card>
                  ) : (
                    <button onClick={() => setConfirming(true)}
                      className="self-start inline-flex items-center gap-2 px-4 py-2.5 border border-danger text-danger font-bold rounded-xl hover:bg-danger/5">
                      <Icon name="gavel" className="text-[18px]" /> Confirmer la rupture (clôture le contrat)
                    </button>
                  )
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
