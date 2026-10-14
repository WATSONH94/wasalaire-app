import { useEffect, useState, type FormEvent, type InputHTMLAttributes } from 'react'
import { useNavigate } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import { Icon } from '../stitch'

type Stage = 'password' | 'change_password' | 'mfa_setup' | 'mfa' | 'recovery'

// Champ de saisie stylé console Stitch.
function Field({ label, hint, ...rest }: { label: string; hint?: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block space-y-1.5">
      <span className="block font-label-lg text-label-lg font-semibold text-ink">{label}</span>
      <input
        className="w-full px-3 py-3 font-subtitle-md text-subtitle-md text-ink placeholder:text-outline bg-white rounded-xl border border-border focus:border-secondary-fixed-dim focus:ring-2 focus:ring-secondary-fixed-dim/30 outline-none transition-all"
        {...rest}
      />
      {hint && <span className="block font-label-md text-label-md text-muted">{hint}</span>}
    </label>
  )
}

function SubmitBtn({ busy, children, disabled }: { busy?: boolean; children: React.ReactNode; disabled?: boolean }) {
  return (
    <button
      type="submit"
      disabled={busy || disabled}
      className="w-full h-12 bg-secondary-fixed-dim hover:bg-secondary-fixed text-primary text-subtitle-md font-extrabold rounded-xl flex items-center justify-center gap-2 transition-all duration-150 shadow-sm active:scale-[0.99] disabled:opacity-60 disabled:pointer-events-none"
    >
      {busy ? 'Veuillez patienter…' : children}
    </button>
  )
}

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

  const STEPS: { key: Stage; n: number; label: string }[] = [
    { key: 'password', n: 1, label: 'Identifiants' },
    { key: 'change_password', n: 2, label: 'Mot de passe' },
    { key: 'mfa_setup', n: 3, label: 'Sécurité' },
  ]
  const activeN = stage === 'mfa' ? 3 : (STEPS.find((s) => s.key === stage)?.n ?? 3)

  return (
    <div className="min-h-screen bg-background text-ink font-body-md text-body-md flex flex-col justify-between selection:bg-secondary-fixed selection:text-ink">
      {/* Header */}
      <header className="w-full py-4 px-6 md:px-12 flex justify-between items-center border-b border-border bg-surface/80 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-secondary-fixed-dim flex items-center justify-center shadow-sm">
            <span className="text-headline-md text-ink font-extrabold leading-none select-none">W</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-headline-md font-extrabold text-primary-container tracking-tight">WaSalaire</span>
            <span className="text-label-md text-muted bg-surface-container px-2 py-0.5 rounded-full">Console</span>
          </div>
        </div>
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-white text-muted text-label-md">
          <span aria-hidden="true">🇧🇯</span>
          <span>République du Bénin</span>
          <span className="text-border">·</span>
          <span className="text-primary-container font-medium">DGI &amp; CNSS</span>
        </div>
      </header>

      {/* Canvas central */}
      <main className="flex-1 flex flex-col justify-center items-center px-4 py-8 md:py-12">
        <div className="w-full max-w-[400px]">
          {/* Fil d'étapes */}
          <div className="mb-4 bg-surface p-1 rounded-xl border border-border flex items-center justify-between shadow-sm">
            {STEPS.map((s) => (
              <div
                key={s.key}
                className={`flex-1 py-1.5 px-2 rounded-lg text-label-md text-center transition-all ${
                  s.n === activeN ? 'bg-primary-container text-on-primary font-bold shadow-sm' : 'text-muted'
                }`}
              >
                {s.n} · {s.label}
              </div>
            ))}
          </div>

          <div className="bg-surface rounded-2xl border border-border p-6 shadow-sm">
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-secondary-fixed-dim text-ink font-extrabold text-[22px] leading-none mb-3 shadow-sm select-none">W</div>
              <h1 className="text-headline-md font-extrabold text-primary-container mb-0.5">
                {stage === 'password' && 'Connexion'}
                {stage === 'change_password' && 'Nouveau mot de passe'}
                {stage === 'mfa_setup' && 'Sécurisez votre compte'}
                {stage === 'recovery' && 'Codes de récupération'}
                {stage === 'mfa' && 'Vérification'}
              </h1>
              <p className="text-label-lg text-muted">Espace cabinet / RH</p>
            </div>

            {error && (
              <div className="mb-4 p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-label-md font-semibold flex items-start gap-2">
                <Icon name="error" className="text-[18px] mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {stage === 'password' && (
              <form onSubmit={doLogin} className="space-y-4">
                <Field label="Adresse e-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" placeholder="vous@cabinet.bj" autoFocus />
                <Field label="Mot de passe" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" placeholder="••••••••••" />
                <SubmitBtn busy={busy}>Se connecter<Icon name="arrow_forward" className="text-[20px]" /></SubmitBtn>
              </form>
            )}

            {stage === 'change_password' && (
              <form onSubmit={doChange} className="space-y-4">
                <p className="text-label-md text-muted">Choisissez un mot de passe personnel : 10 caractères minimum, avec majuscule, minuscule et chiffre.</p>
                <Field label="Nouveau mot de passe" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} required autoComplete="new-password" />
                <Field label="Confirmer" type="password" value={newPw2} onChange={(e) => setNewPw2(e.target.value)} required autoComplete="new-password" />
                <SubmitBtn busy={busy}>Valider<Icon name="check" className="text-[20px]" /></SubmitBtn>
              </form>
            )}

            {stage === 'mfa_setup' && (
              <form onSubmit={doConfirm} className="space-y-4">
                <p className="text-label-md text-muted text-center">Scannez ce QR code dans votre application Authenticator, puis saisissez le code à 6 chiffres.</p>
                <div className="flex justify-center">
                  {setup ? (
                    <div className="bg-white p-2.5 rounded-xl border border-border">
                      <QRCodeSVG value={setup.otpauth_uri} size={168} />
                    </div>
                  ) : (
                    <span className="spinner" />
                  )}
                </div>
                {setup && (
                  <p className="text-center text-label-md text-muted">
                    Clé manuelle : <code className="text-ink font-semibold">{setup.secret}</code>
                  </p>
                )}
                <Field label="Code à 6 chiffres" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} placeholder="______" required autoFocus />
                <SubmitBtn busy={busy} disabled={!setup}>Activer la double authentification</SubmitBtn>
              </form>
            )}

            {stage === 'recovery' && (
              <div className="space-y-4">
                <p className="text-label-md text-muted text-center">Conservez ces codes en lieu sûr. Chacun est utilisable une seule fois si vous perdez votre téléphone.</p>
                <div className="grid grid-cols-2 gap-2 p-3 rounded-xl bg-surface-container-low border border-border font-mono text-body-md">
                  {recovery.map((c) => <span key={c} className="text-ink">{c}</span>)}
                </div>
                <button
                  onClick={() => pending && finish(pending.token, pending.companies, pending.roles)}
                  className="w-full h-12 bg-secondary-fixed-dim hover:bg-secondary-fixed text-primary text-subtitle-md font-extrabold rounded-xl flex items-center justify-center gap-2 shadow-sm active:scale-[0.99]"
                >
                  J'ai noté mes codes — continuer
                </button>
              </div>
            )}

            {stage === 'mfa' && (
              <form onSubmit={doVerify} className="space-y-4">
                <p className="text-label-md text-muted text-center">Entrez le code à 6 chiffres de votre application Authenticator (ou un code de récupération).</p>
                <Field label="Code à 6 chiffres" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} placeholder="______" required autoFocus />
                <SubmitBtn busy={busy}>Se connecter<Icon name="login" className="text-[20px]" /></SubmitBtn>
              </form>
            )}

            <div className="mt-4 p-3 rounded-xl bg-white/70 border border-border flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center shrink-0 text-primary-container">
                <Icon name="verified" className="text-[18px]" />
              </div>
              <p className="text-label-md text-muted leading-tight">
                Connexion sécurisée conforme aux directives <strong>DGI Bénin</strong> et <strong>APDP</strong>.
              </p>
            </div>
          </div>
        </div>
      </main>

      <footer className="w-full py-4 px-6 text-center border-t border-border bg-surface text-label-md text-muted">
        <div className="flex flex-col sm:flex-row items-center justify-center gap-2 sm:gap-4">
          <span>Besoin d'assistance ? Support cabinet</span>
          <span className="hidden sm:inline text-border">·</span>
          <a className="text-primary-container font-semibold hover:underline" href="mailto:support@wasalaire.bj">support@wasalaire.bj</a>
          <span className="hidden sm:inline text-border">·</span>
          <span>Cotonou, République du Bénin</span>
        </div>
      </footer>
    </div>
  )
}
