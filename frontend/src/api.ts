// Client API WaSalaire. Base RELATIVE par défaut (même origine que l'API en prod,
// aucune URL codée en dur) ; surchargeable par VITE_API_BASE si besoin.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
const TOKEN_KEY = 'wasalaire.token'

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(t: string | null): void {
  try { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY) } catch { /* noop */ }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

type ReqOpts = { method?: string; body?: unknown; auth?: boolean; bearer?: string }

async function request<T>(path: string, opts: ReqOpts = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (opts.bearer) {
    headers['Authorization'] = `Bearer ${opts.bearer}`
  } else if (opts.auth !== false) {
    const t = getToken()
    if (t) headers['Authorization'] = `Bearer ${t}`
  }
  const res = await fetch(`${BASE}${path}`, {
    method: opts.method ?? 'GET',
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  })
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    const detail = data && (data.detail ?? data.message)
    const msg = typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : `Erreur ${res.status}`
    throw new ApiError(res.status, msg)
  }
  return data as T
}

const qs = (o: Record<string, string | undefined>) =>
  '?' + Object.entries(o).filter(([, v]) => v !== undefined && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(v as string)}`).join('&')

export interface Session { token: string; user_id: string; companies: string[]; roles: string[]; email?: string | null; platform_role?: string | null; mfa_enrolled?: boolean }
export interface Me { user_id: string; companies: string[]; roles: string[]; email?: string | null; platform_role?: string | null; mfa_enrolled?: boolean; mfa_enforced?: boolean }
export interface Company { id: string; raison_sociale?: string; nom?: string; ifu?: string | null }
export interface Employee { id: string; nom: string; matricule: string; methode_paiement?: string; salaire_base?: number | null }
export interface Payslip { nom: string; brut: number; base_its: number; net: number; cout_employeur: number; verrouille: boolean }
export interface Anomaly { nom?: string; gravite: string; message?: string; libelle?: string; code?: string }
export interface Controls { run_id: string; bloquants: number; avertissements: number; anomalies: Anomaly[] }
export interface PlatformUser { id: string; email: string; platform_role: string | null; statut: string; totp_enrolled: boolean; must_change_password: boolean }
export interface PlatformSubscription { workspace_id: string; workspace: string; type: string; plan: string; statut: string; is_beta: boolean }
export interface Plan { code: string; libelle: string; is_public: boolean; limites: Record<string, unknown> }
export interface OrgNode { id: string; type: string; nom: string }

export const api = {
  // ── Auth
  requestOtp: (telephone: string, canal: 'sms' | 'whatsapp') =>
    request<{ sent: boolean; dev_code?: string; statut_envoi?: string; avertissement?: string }>(
      '/v1/auth/request-otp', { method: 'POST', body: { telephone, canal }, auth: false }),
  verifyOtp: (telephone: string, code: string) =>
    request<Session>('/v1/auth/verify-otp', { method: 'POST', body: { telephone, code }, auth: false }),
  me: () => request<Me>('/v1/me'),

  // ── Auth web : email + mot de passe + MFA TOTP
  login: (email: string, password: string) =>
    request<{ token: string; stage: string; user_id: string }>(
      '/v1/auth/login', { method: 'POST', body: { email, password }, auth: false }),
  changePassword: (bearer: string, new_password: string, current_password?: string) =>
    request<{ token: string; stage: string }>(
      '/v1/auth/password/change', { method: 'POST', body: { new_password, current_password }, bearer }),
  mfaSetup: (bearer: string) =>
    request<{ secret: string; otpauth_uri: string }>('/v1/auth/mfa/setup', { method: 'POST', bearer }),
  mfaConfirm: (bearer: string, code: string) =>
    request<{ token: string; recovery_codes: string[]; companies: string[]; roles: string[] }>(
      '/v1/auth/mfa/confirm', { method: 'POST', body: { code }, bearer }),
  mfaVerify: (bearer: string, code: string) =>
    request<{ token: string; companies: string[]; roles: string[] }>(
      '/v1/auth/mfa/verify', { method: 'POST', body: { code }, bearer }),

  // ── Plateforme (admin)
  platformUsers: () => request<{ users: PlatformUser[] }>('/v1/platform/users'),
  platformSubscriptions: () => request<{ subscriptions: PlatformSubscription[] }>('/v1/platform/subscriptions'),
  platformPlans: () => request<{ plans: Plan[] }>('/v1/platform/plans'),
  setSubscription: (workspace_id: string, plan_code: string, is_beta = false) =>
    request<{ workspace_id: string; plan: string; is_beta: boolean }>(
      '/v1/platform/subscription', { method: 'PUT', body: { workspace_id, plan_code, is_beta } }),

  // ── Sociétés & salariés
  companies: () => request<{ companies: Company[] }>('/v1/companies'),
  adminNodes: () => request<{ nodes: OrgNode[] }>('/v1/org/admin-nodes'),
  createCompany: (parent_node_id: string, raison_sociale: string, ifu?: string | null) =>
    request<{ company_id: string }>('/v1/companies', { method: 'POST', body: { parent_node_id, raison_sociale, ifu: ifu || null } }),
  employees: (companyId: string) =>
    request<{ company_id: string; employes: Employee[] }>('/v1/employees' + qs({ company_id: companyId })),
  createEmployee: (body: {
    company_id: string; matricule: string; nom: string; salaire_base: number
    type_contrat?: string; methode_paiement?: string; num_cnss?: string | null
  }) => request<{ employee_id: string; matricule: string }>('/v1/employees', { method: 'POST', body }),

  // ── Cycle de paie
  openPeriod: (body: { company_id: string; mois: number; annee: number }) =>
    request<{ period_id: string; statut: string }>('/v1/periods', { method: 'POST', body }),
  addVariable: (body: { company_id: string; period_id: string; employee_id: string; type: string; montant: number }) =>
    request<{ variable_id: string }>('/v1/periods/variables', { method: 'POST', body }),
  calculate: (body: { company_id: string; period_id: string; periode: string }) =>
    request<{ run_id: string; bulletins: number }>('/v1/periods/calculate', { method: 'POST', body }),
  controls: (runId: string) => request<Controls>(`/v1/runs/${runId}/controls`),
  closeRun: (runId: string, periodId: string) =>
    request<{ run_id: string; statut: string }>(`/v1/runs/${runId}/close` + qs({ period_id: periodId }), { method: 'POST' }),
  payslips: (runId: string) => request<{ run_id: string; bulletins: Payslip[] }>(`/v1/runs/${runId}/payslips`),
  declaration: (runId: string) => request<Record<string, number | string>>(`/v1/runs/${runId}/declaration`),
  reporting: (companyId: string) => request<Record<string, number>>('/v1/reporting' + qs({ company_id: companyId })),
}

export const fcfa = (n: number | null | undefined) =>
  n == null ? '—' : new Intl.NumberFormat('fr-FR').format(Math.round(n)) + ' FCFA'
