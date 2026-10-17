import { useEffect, useState } from 'react'
import { api, ApiError, type GovernancePolicy, type Me } from '../api'
import { Badge, Card, Icon } from '../stitch'

function Toggle({ on, onClick, disabled }: { on: boolean; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled} role="switch" aria-checked={on}
      className={`relative w-12 h-7 rounded-full transition-colors shrink-0 disabled:opacity-50 ${on ? 'bg-secondary' : 'bg-outline-variant'}`}>
      <span className={`absolute top-1 left-1 w-5 h-5 rounded-full bg-white shadow transition-transform ${on ? 'translate-x-5' : ''}`} />
    </button>
  )
}

const ROLES = [
  { r: 'Administrateur', scope: 'Cabinet (global)', priv: 'Configuration, utilisateurs, audit, validation, export', ic: 'shield_person' },
  { r: 'Gestionnaire de paie', scope: 'Sociétés assignées', priv: 'Calcul, variables, déclarations, virements', ic: 'payments' },
  { r: 'Responsable RH', scope: 'Établissement', priv: 'Salariés, variables, congés, heures sup, contrats', ic: 'groups' },
  { r: 'Comptable', scope: 'Société', priv: 'Écritures SYSCOHADA, journal de paie, export FEC/CSV', ic: 'account_balance' },
  { r: 'Auditeur / Contrôle', scope: 'Société', priv: 'Lecture seule : registres, contrôle conformité', ic: 'visibility' },
  { r: 'Salarié (self-service)', scope: 'Soi-même', priv: 'Bulletins, récap, demandes de congés', ic: 'person' },
]

export default function Parametres() {
  const [me, setMe] = useState<Me | null>(null)
  const [gov, setGov] = useState<GovernancePolicy | null>(null)
  const [govError, setGovError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    api.me().then(setMe).catch(() => undefined)
    api.getGovernance().then(setGov).catch((e) => setGovError(
      e instanceof ApiError && e.status === 403
        ? 'La séparation des tâches est configurable par l’administrateur du cabinet.'
        : 'La séparation des tâches se règle au niveau de chaque société abonnée.'))
  }, [])

  const toggleGov = (champ: 'four_eyes_calcul_validation' | 'four_eyes_validation_paiement') => {
    if (!gov) return
    setBusy(champ); setGovError(null)
    api.setGovernance(champ, !gov[champ])
      .then(setGov)
      .catch((e) => setGovError(e instanceof ApiError ? e.message : 'Erreur réseau'))
      .finally(() => setBusy(null))
  }

  const ITS = [
    ['≤ 60 000 FCFA', '0 % (exonéré)'], ['60 001 – 150 000', '10 %'], ['150 001 – 250 000', '15 %'],
    ['250 001 – 500 000', '19 %'], ['> 500 000', '30 %'],
  ]

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-6">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-headline-sm font-extrabold text-ink tracking-tight">Paramètres &amp; Configuration légale</h2>
          <Badge tone="success" icon="cloud_done">Règles fiscales Bénin synchronisées</Badge>
        </div>
        <p className="text-body-md text-muted mt-1 max-w-2xl">Compte, gouvernance (séparation des tâches), matrice des rôles (RBAC) et barèmes réglementaires versionnés.</p>
      </Card>

      {/* Compte */}
      {me && (
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4"><Icon name="account_circle" className="text-muted" /><h3 className="text-subtitle-md font-bold text-ink">Mon espace</h3></div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div><div className="text-label-md text-muted">Identifiant</div><div className="font-bold text-ink break-all">{me.email ?? me.user_id}</div></div>
            <div><div className="text-label-md text-muted">Rôle plateforme</div><div className="font-bold text-ink capitalize">{me.platform_role ?? 'Client'}</div></div>
            <div><div className="text-label-md text-muted">Habilitations</div><div className="font-bold text-ink">{me.roles.length ? me.roles.join(' · ') : '—'}</div></div>
          </div>
        </Card>
      )}

      {/* Gouvernance — séparation des tâches (éditable) */}
      <Card className="p-5">
        <div className="flex items-center gap-2 mb-1"><Icon name="verified_user" className="text-secondary" /><h3 className="text-subtitle-md font-bold text-ink">Gouvernance &amp; séparation des tâches</h3></div>
        <p className="text-label-md text-muted mb-4">Le principe des « 4 yeux » impose qu'un second utilisateur intervienne sur les opérations sensibles — sécurité anti-fraude recommandée.</p>
        {govError ? (
          <div className="p-3 rounded-xl bg-warm-sand/20 border border-warm-sand/50 text-ink text-label-md flex items-center gap-2"><Icon name="lock" className="text-warning" />{govError}</div>
        ) : gov ? (
          <div className="flex flex-col gap-3">
            {([
              { k: 'four_eyes_calcul_validation', t: 'Validation du calcul par un tiers', s: 'La clôture d’un cycle doit être validée par un autre utilisateur que celui qui a calculé.' },
              { k: 'four_eyes_validation_paiement', t: 'Validation du paiement par un tiers', s: 'Le valideur de la clôture ne peut pas aussi lancer le décaissement.' },
            ] as const).map((g) => (
              <div key={g.k} className="flex items-center justify-between gap-4 p-3 rounded-xl border border-border">
                <div><div className="font-bold text-ink">{g.t}</div><div className="text-label-md text-muted">{g.s}</div></div>
                <Toggle on={gov[g.k]} onClick={() => toggleGov(g.k)} disabled={busy === g.k} />
              </div>
            ))}
          </div>
        ) : <div className="flex items-center gap-2 text-muted"><span className="spinner" /> Chargement…</div>}
      </Card>

      {/* RBAC — référence */}
      <Card className="p-0 overflow-hidden">
        <div className="p-5 border-b border-border flex items-center gap-2"><Icon name="admin_panel_settings" className="text-primary" /><h3 className="text-subtitle-md font-bold text-ink">Accès &amp; rôles (RBAC × périmètre)</h3></div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead><tr className="bg-surface-container-low border-b border-border text-label-md font-bold text-muted uppercase tracking-wider">
              <th className="py-3 px-5">Rôle</th><th className="py-3 px-4">Portée</th><th className="py-3 px-4">Droits &amp; privilèges</th>
            </tr></thead>
            <tbody className="divide-y divide-border text-body-md text-ink">
              {ROLES.map((r, i) => (
                <tr key={i} className="hover:bg-primary-fixed/10">
                  <td className="py-3 px-5"><div className="flex items-center gap-2 font-bold"><Icon name={r.ic} className="text-muted text-[18px]" />{r.r}</div></td>
                  <td className="py-3 px-4"><Badge tone="neutral">{r.scope}</Badge></td>
                  <td className="py-3 px-4 text-muted">{r.priv}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="p-4 text-label-md text-muted flex items-start gap-1.5"><Icon name="info" className="text-[16px] mt-0.5" />L'isolation multi-entités (RLS) garantit l'étanchéité des données salariales selon le périmètre accordé.</p>
      </Card>

      {/* Barèmes réglementaires versionnés — référence */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3"><h3 className="text-subtitle-md font-bold text-ink">SMIG &amp; cotisations</h3><Badge tone="success">Taux officiels</Badge></div>
          <div className="flex items-baseline gap-2 mb-3"><span className="text-headline-sm font-extrabold text-primary">52 000</span><span className="text-muted font-semibold">FCFA</span><span className="text-label-md text-muted">SMIG mensuel (Décret 2022-692)</span></div>
          <div className="flex flex-col">
            {[['CNSS Vieillesse / Retraite', '6,4 % pat. + 3,6 % sal.'], ['Prestations familiales (PF)', '9 % patronal'], ['Accidents du travail (AT/MP)', '1 à 4 % (notifié)'], ['Versement Patronal (VPS)', '4 %'], ['Plafond d’assiette CNSS', 'Aucun plafond']].map((x, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-border last:border-0"><span className="text-body-md text-muted">{x[0]}</span><span className="font-bold text-ink tabular-nums">{x[1]}</span></div>
            ))}
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3"><h3 className="text-subtitle-md font-bold text-ink">Barème progressif ITS</h3><Badge tone="neutral">CGI Art. 125</Badge></div>
          <div className="flex flex-col">
            {ITS.map((x, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-border last:border-0"><span className="text-body-md text-muted">{x[0]}</span><span className="font-bold text-ink tabular-nums">{x[1]}</span></div>
            ))}
          </div>
          <p className="text-label-md text-muted mt-3">Abattements pour charges de famille appliqués automatiquement. AMO (Décret 2025-672) : part patronale 80 % / salariale 20 %, échéance 29/10/2026.</p>
        </Card>
      </div>
    </div>
  )
}
