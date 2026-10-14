import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import { Brand, Button, Field } from '../ui'

type Stage = 'password' | 'change_password' | 'mfa_setup' | 'mfa' | 'recovery'

export default function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [stage, setStage] = useState<Stage>('password')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pre, setPre] = useState('')
  const [userId, setUserId] = useState('')
  const [newPw, setNewPw] = useState('')
  const [newPw2, setNewPw2] = useState('')
  const [code, setCode] = useState('')
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null)
  const [recovery, setRecovery] = useState<string[]>([])
  const [pending, setPending] = useState<{ token: string; companies: string[]; roles: string[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Dès qu'on entre en enrôlement MFA, on récupère le secret + QR.
  useEffect(() => {
    if (stage === 'mfa_setup' && pre && !setup) {
      api.mfaSetup(pre).then(setSetup).catch((e) => setError(e instanceof ApiError ? e.message : 'Erreur réseau'))
    }
  }, [stage, pre, setup])

  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : 'Erreur réseau')
  const finish = (token: string, companies: string[], roles: string[]) => {
    login({ token, user_id: userId, companies, roles }); nav('/', { replace: true })
  }

  async function doLogin(e: FormEvent) {
    e.preventDefault(); setError(null); setBusy(true)
    try {
      const r = await api.login(email.trim(), password)
      setPre(r.token); setUserId(r.user_id); setStage(r.stage as Stage); setPassword('')
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  async function doChange(e: FormEvent) {
    e.preventDefault(); setError(null)
    if (newPw !== newPw2) { setError('Les deux mots de passe ne correspondent pas.'); return }
    setBusy(true)
    try {
      const r = await api.changePassword(pre, newPw)
      setPre(r.token); setStage(r.stage as Stage); setNewPw(''); setNewPw2('')
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  async function doConfirm(e: FormEvent) {
    e.preventDefault(); setError(null); setBusy(true)
    try {
      const r = await api.mfaConfirm(pre, code.trim())
      setRecovery(r.recovery_codes); setPending({ token: r.token, companies: r.companies, roles: r.roles })
      setCode(''); setStage('recovery')
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  async function doVerify(e: FormEvent) {
    e.preventDefault(); setError(null); setBusy(true)
    try {
      const r = await api.mfaVerify(pre, code.trim())
      finish(r.token, r.companies, r.roles)
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}><Brand height={40} /></div>
        {error && <div className="error mt8" style={{ marginBottom: 12 }}>{error}</div>}

        {stage === 'password' && (
          <form onSubmit={doLogin}>
            <h2 style={{ textAlign: 'center' }}>Connexion</h2>
            <p className="muted" style={{ textAlign: 'center', marginBottom: 18 }}>Accédez à votre espace WaSalaire.</p>
            <Field label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
            <Field label="Mot de passe" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
            <Button type="submit" block disabled={busy}>{busy ? 'Connexion…' : 'Se connecter'}</Button>
          </form>
        )}

        {stage === 'change_password' && (
          <form onSubmit={doChange}>
            <h2 style={{ textAlign: 'center' }}>Nouveau mot de passe</h2>
            <p className="muted" style={{ textAlign: 'center', marginBottom: 18 }}>Choisissez un mot de passe personnel (10+ caractères, majuscule, minuscule, chiffre).</p>
            <Field label="Nouveau mot de passe" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} required autoComplete="new-password" />
            <Field label="Confirmer" type="password" value={newPw2} onChange={(e) => setNewPw2(e.target.value)} required autoComplete="new-password" />
            <Button type="submit" block disabled={busy}>{busy ? 'Enregistrement…' : 'Valider'}</Button>
          </form>
        )}

        {stage === 'mfa_setup' && (
          <form onSubmit={doConfirm}>
            <h2 style={{ textAlign: 'center' }}>Sécurisez votre compte</h2>
            <p className="muted" style={{ textAlign: 'center', marginBottom: 14 }}>Scannez ce QR code dans votre application Authenticator, puis saisissez le code à 6 chiffres.</p>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
              {setup ? <div style={{ background: '#fff', padding: 10, borderRadius: 12, border: '1px solid var(--line)' }}>
                <QRCodeSVG value={setup.otpauth_uri} size={168} />
              </div> : <span className="spinner" />}
            </div>
            {setup && <p className="muted" style={{ textAlign: 'center', fontSize: '.78rem', marginBottom: 14 }}>Clé manuelle : <code>{setup.secret}</code></p>}
            <Field label="Code à 6 chiffres" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} placeholder="______" required autoFocus />
            <Button type="submit" block disabled={busy || !setup}>{busy ? 'Vérification…' : 'Activer la double authentification'}</Button>
          </form>
        )}

        {stage === 'recovery' && (
          <div>
            <h2 style={{ textAlign: 'center' }}>Codes de récupération</h2>
            <p className="muted" style={{ textAlign: 'center', marginBottom: 14 }}>Conservez ces 8 codes en lieu sûr. Chacun est utilisable une seule fois si vous perdez votre téléphone.</p>
            <div className="card" style={{ background: 'var(--bg)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontFamily: 'monospace', fontSize: '.95rem', marginBottom: 16 }}>
              {recovery.map((c) => <span key={c}>{c}</span>)}
            </div>
            <Button block onClick={() => pending && finish(pending.token, pending.companies, pending.roles)}>J'ai noté mes codes — continuer</Button>
          </div>
        )}

        {stage === 'mfa' && (
          <form onSubmit={doVerify}>
            <h2 style={{ textAlign: 'center' }}>Vérification</h2>
            <p className="muted" style={{ textAlign: 'center', marginBottom: 18 }}>Entrez le code à 6 chiffres de votre application Authenticator.</p>
            <Field label="Code à 6 chiffres" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} placeholder="______" required autoFocus />
            <Button type="submit" block disabled={busy}>{busy ? 'Vérification…' : 'Se connecter'}</Button>
            <p className="muted" style={{ textAlign: 'center', fontSize: '.78rem', marginTop: 10 }}>Vous pouvez aussi saisir un code de récupération.</p>
          </form>
        )}
      </div>
    </div>
  )
}
