import { useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import { Badge, Button, Card, Field, Icon, PageHeader } from '../stitch'

const ROLE_LABELS: Record<string, string> = {
  admin_plateforme: 'Administrateur plateforme',
  super_admin: 'Super-administrateur',
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
    try {
      await api.changePassword(session.token, npw, cur)
      setMsg({ ok: true, text: 'Mot de passe mis à jour.' })
      setCur(''); setNpw(''); setNpw2('')
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiError ? err.message : 'Erreur réseau' })
    } finally { setBusy(false) }
  }

  const initials = (session?.email ?? 'WS').slice(0, 2).toUpperCase()
  const platformLabel = session?.platform_role && session.platform_role !== 'none'
    ? ROLE_LABELS[session.platform_role] ?? session.platform_role
    : null

  return (
    <>
      <PageHeader title="Mon compte" subtitle="Identité, sécurité et accès de votre profil WaSalaire." />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Identité */}
        <Card className="p-6 flex flex-col items-center text-center gap-3">
          <div className="w-20 h-20 rounded-2xl bg-primary text-surface-container-lowest flex items-center justify-center text-headline-lg font-extrabold">
            {initials}
          </div>
          <div>
            <div className="text-subtitle-lg font-subtitle-lg text-ink break-all">{session?.email ?? 'Utilisateur'}</div>
            <div className="text-label-md text-muted mt-0.5 font-mono break-all">ID {session?.user_id?.slice(0, 8)}…</div>
          </div>
          <div className="flex flex-wrap gap-2 justify-center">
            {platformLabel && <Badge tone="primary" icon="shield">{platformLabel}</Badge>}
            {session?.roles?.map((r) => <Badge key={r} tone="neutral">{r}</Badge>)}
          </div>
          <div className="w-full pt-3 border-t border-border flex items-center justify-between text-label-md">
            <span className="text-muted">Sociétés accessibles</span>
            <span className="font-bold text-ink tabular-nums">{session?.companies?.length ?? 0}</span>
          </div>
        </Card>

        {/* Sécurité */}
        <Card className="lg:col-span-2 p-6 flex flex-col gap-5">
          <h3 className="text-subtitle-lg font-subtitle-lg text-ink flex items-center gap-2">
            <Icon name="security" className="text-secondary" /> Sécurité
          </h3>

          {/* MFA */}
          <div className="flex items-center justify-between p-4 rounded-xl bg-surface-container-low border border-border">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-secondary/10 text-secondary flex items-center justify-center">
                <Icon name="phonelink_lock" className="text-[22px]" />
              </div>
              <div>
                <div className="text-subtitle-md font-bold text-ink">Double authentification (TOTP)</div>
                <div className="text-label-md text-muted">Application Authenticator</div>
              </div>
            </div>
            <Badge tone={session?.mfa_enrolled ? 'success' : 'warning'} icon={session?.mfa_enrolled ? 'check_circle' : 'warning'}>
              {session?.mfa_enrolled ? 'Activée' : 'À activer'}
            </Badge>
          </div>

          {/* Changement mot de passe */}
          <form onSubmit={changePw} className="flex flex-col gap-4">
            <div className="text-subtitle-md font-bold text-ink">Changer le mot de passe</div>
            {msg && (
              <div className={`p-3 rounded-xl text-label-md font-semibold border ${msg.ok ? 'bg-success/10 border-success/20 text-success' : 'bg-danger/10 border-danger/20 text-danger'}`}>
                {msg.text}
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Mot de passe actuel" type="password" value={cur} onChange={(e) => setCur(e.target.value)} required autoComplete="current-password" className="sm:col-span-2" />
              <Field label="Nouveau mot de passe" type="password" value={npw} onChange={(e) => setNpw(e.target.value)} required autoComplete="new-password" />
              <Field label="Confirmer" type="password" value={npw2} onChange={(e) => setNpw2(e.target.value)} required autoComplete="new-password" />
            </div>
            <p className="text-label-md text-muted">10 caractères minimum, avec majuscule, minuscule et chiffre.</p>
            <div>
              <Button variant="primary" type="submit" disabled={busy} icon="lock_reset">{busy ? 'Enregistrement…' : 'Mettre à jour'}</Button>
            </div>
          </form>

          {/* Session */}
          <div className="pt-4 border-t border-border flex items-center justify-between">
            <div className="flex items-center gap-2 text-label-md text-muted">
              <Icon name="devices" className="text-[18px]" /> Session actuelle sur cet appareil
            </div>
            <Button variant="ghost" icon="logout" onClick={logout} className="text-danger">Se déconnecter</Button>
          </div>
        </Card>
      </div>
    </>
  )
}
