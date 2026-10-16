import { useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import { Icon } from '../stitch'

const ROLE_LABELS: Record<string, string> = {
  admin_plateforme: 'Administrateur plateforme', super_admin: 'Super-administrateur',
  support: 'Support technique', conformite: 'Responsable conformité', commercial: 'Responsable commercial',
}

export default function MonCompte() {
  const { session, logout } = useAuth()
  const [cur, setCur] = useState('')
  const [npw, setNpw] = useState('')
  const [npw2, setNpw2] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  async function changePw(e: FormEvent) {
    e.preventDefault(); setMsg(null)
    if (npw !== npw2) { setMsg({ ok: false, text: 'Les deux mots de passe ne correspondent pas.' }); return }
    if (!session) return
    setBusy(true)
    try { await api.changePassword(session.token, npw, cur); setMsg({ ok: true, text: 'Mot de passe mis à jour.' }); setCur(''); setNpw(''); setNpw2('') }
    catch (err) { setMsg({ ok: false, text: err instanceof ApiError ? err.message : 'Erreur réseau' }) } finally { setBusy(false) }
  }

  const initials = (session?.email ?? 'WS').slice(0, 2).toUpperCase()
  const platformLabel = session?.platform_role && session.platform_role !== 'none' ? ROLE_LABELS[session.platform_role] ?? session.platform_role : null

  return (
    <div className="space-y-6">
      {/* En-tête */}
      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
        <div>
          <div className="text-label-md text-muted flex items-center gap-1.5">Espace personnel <Icon name="chevron_right" className="text-[14px]" /> Identité &amp; Sécurité</div>
          <h1 className="text-headline-lg font-headline-lg text-ink font-extrabold tracking-tight">Mon compte</h1>
          <p className="text-body-md text-muted mt-1 max-w-2xl">Gestion du profil, sécurité des accès et double authentification (MFA).</p>
        </div>
        <button onClick={logout} className="inline-flex items-center gap-2 px-4 py-2 border border-danger/30 text-danger font-bold rounded-xl hover:bg-danger/5"><Icon name="logout" className="text-base" />Se déconnecter</button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Colonne principale */}
        <div className="lg:col-span-2 space-y-6">
          {/* Profil */}
          <div className="bg-surface rounded-2xl border border-border shadow-sm p-6">
            <div className="flex items-start gap-4">
              <div className="w-16 h-16 rounded-2xl bg-primary-container text-surface-container-lowest flex items-center justify-center text-headline-md font-black shadow-md">{initials}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-subtitle-lg font-subtitle-lg font-bold text-ink break-all">{session?.email ?? 'Utilisateur'}</h2>
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-secondary-fixed/30 text-secondary"><Icon name="verified" className="text-xs" />Vérifié</span>
                </div>
                <div className="text-body-md text-muted mt-0.5">{platformLabel ?? (session?.roles?.length ? session.roles.join(' · ') : 'Gestionnaire de paie')}</div>
                <div className="text-label-md text-muted font-mono mt-1">ID {session?.user_id?.slice(0, 8)}…</div>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-5">
              <div className="p-3 rounded-lg bg-surface-container-low/60 border border-border">
                <span className="text-label-md text-muted block">Rôle &amp; périmètre</span>
                <span className="font-bold text-ink">{platformLabel ? 'Équipe WaSalaire (interne)' : 'Organisation cliente'}</span>
                <span className="text-[11px] text-muted block mt-0.5">{session?.companies?.length ?? 0} société(s) accessible(s)</span>
              </div>
              <div className="p-3 rounded-lg bg-surface-container-low/60 border border-border">
                <span className="text-label-md text-muted block">Langue &amp; juridiction</span>
                <span className="font-bold text-ink">Français (Bénin / UEMOA)</span>
                <span className="text-[11px] text-muted block mt-0.5">Afrique de l’Ouest / Cotonou (UTC+1)</span>
              </div>
            </div>
          </div>

          {/* MFA + mot de passe */}
          <div className="bg-surface rounded-2xl border border-border shadow-sm p-6 space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-secondary/10 text-secondary flex items-center justify-center"><Icon name="shield" className="text-[22px]" /></div>
                <div><h3 className="text-subtitle-md font-bold text-ink">Authentification à deux facteurs (MFA)</h3><p className="text-label-md text-muted">Protection obligatoire des accès.</p></div>
              </div>
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-label-md font-bold ${session?.mfa_enrolled ? 'bg-success/10 text-success' : 'bg-warning/15 text-warning'}`}><span className={`w-2 h-2 rounded-full ${session?.mfa_enrolled ? 'bg-success' : 'bg-warning'}`}></span>{session?.mfa_enrolled ? 'Actif & protégé' : 'À activer'}</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="p-4 rounded-xl bg-surface-container-low/50 border border-border">
                <div className="flex items-center gap-2 text-ink font-bold"><Icon name="key" className="text-secondary" />Application TOTP</div>
                <p className="text-label-md text-muted mt-1">Générateur local (Google Authenticator / Authy). Code à 6 chiffres à chaque connexion.</p>
              </div>
              <div className="p-4 rounded-xl bg-surface-container-low/50 border border-border">
                <div className="flex items-center gap-2 text-ink font-bold"><Icon name="lock" className="text-secondary" />Codes de secours</div>
                <p className="text-label-md text-muted mt-1">Générés lors de l’activation MFA. Accès temporaire en cas de perte du téléphone.</p>
              </div>
            </div>

            <form onSubmit={changePw} className="pt-4 border-t border-border space-y-4">
              <div className="text-subtitle-md font-bold text-ink">Changer le mot de passe</div>
              {msg && <div className={`p-3 rounded-xl text-label-md font-semibold border ${msg.ok ? 'bg-success/10 border-success/20 text-success' : 'bg-danger/10 border-danger/20 text-danger'}`}>{msg.text}</div>}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <label className="sm:col-span-2 space-y-1.5"><span className="block text-label-lg font-semibold text-ink">Mot de passe actuel</span><input type="password" value={cur} onChange={(e) => setCur(e.target.value)} required autoComplete="current-password" className="w-full px-3 py-2.5 bg-white rounded-xl border border-border outline-none focus:border-secondary" /></label>
                <label className="space-y-1.5"><span className="block text-label-lg font-semibold text-ink">Nouveau</span><input type="password" value={npw} onChange={(e) => setNpw(e.target.value)} required autoComplete="new-password" className="w-full px-3 py-2.5 bg-white rounded-xl border border-border outline-none focus:border-secondary" /></label>
                <label className="space-y-1.5"><span className="block text-label-lg font-semibold text-ink">Confirmer</span><input type="password" value={npw2} onChange={(e) => setNpw2(e.target.value)} required autoComplete="new-password" className="w-full px-3 py-2.5 bg-white rounded-xl border border-border outline-none focus:border-secondary" /></label>
              </div>
              <p className="text-label-md text-muted">10 caractères minimum, avec majuscule, minuscule et chiffre.</p>
              <button type="submit" disabled={busy} className="inline-flex items-center gap-2 px-4 py-2.5 bg-secondary-fixed text-ink font-extrabold rounded-xl hover:bg-secondary-fixed-dim disabled:opacity-50"><Icon name="lock_reset" className="text-[18px]" />{busy ? 'Enregistrement…' : 'Mettre à jour'}</button>
            </form>
          </div>
        </div>

        {/* Colonne latérale */}
        <div className="space-y-6">
          <div className="bg-surface rounded-2xl border border-border shadow-sm p-5">
            <h3 className="text-subtitle-md font-bold text-ink mb-3">Session active</h3>
            <div className="p-4 rounded-xl bg-surface-container-low/50 border border-border">
              <div className="flex items-center justify-between"><div className="flex items-center gap-2 text-ink font-bold"><Icon name="computer" className="text-secondary" />Cet appareil</div>
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-secondary-fixed/30 text-secondary">Cette session</span></div>
              <p className="text-label-md text-muted mt-1">Connexion sécurisée (email + MFA). Session liée à ce navigateur.</p>
            </div>
            <button onClick={logout} className="w-full mt-3 inline-flex items-center justify-center gap-2 px-4 py-2 border border-border text-ink font-bold rounded-xl hover:bg-surface-container"><Icon name="logout" className="text-base" />Fermer la session</button>
          </div>
          <div className="bg-surface rounded-2xl border border-border shadow-sm p-5">
            <div className="flex items-center gap-2 text-ink font-bold"><Icon name="enhanced_encryption" className="text-secondary" />Chiffrement &amp; Sécurité</div>
            <p className="text-body-md text-muted mt-2">Mots de passe hachés (argon2), secrets MFA chiffrés (Fernet). Accès aux données de paie protégés et conformes aux directives APDP Bénin.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
