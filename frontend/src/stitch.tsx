// Primitives du design system WaSalaire (maquettes Stitch — console cabinet).
// Icônes Material Symbols + briques réutilisées par tous les écrans.
import type { CSSProperties, ReactNode } from 'react'

export function Icon({
  name,
  className = '',
  fill = false,
  style,
}: {
  name: string
  className?: string
  fill?: boolean
  style?: CSSProperties
}) {
  return (
    <span
      className={`material-symbols-outlined ${className}`}
      style={{ fontVariationSettings: fill ? "'FILL' 1" : undefined, ...style }}
      aria-hidden="true"
    >
      {name}
    </span>
  )
}

// Carte blanche standard (surface + bord + ombre douce).
export function Card({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={`bg-surface rounded-2xl border border-border shadow-sm ${className}`}
    >
      {children}
    </div>
  )
}

type Tone = 'success' | 'warning' | 'danger' | 'secondary' | 'primary' | 'neutral'

const TONE: Record<Tone, string> = {
  success: 'bg-success/10 text-success',
  warning: 'bg-warning/15 text-warning',
  danger: 'bg-danger/10 text-danger',
  secondary: 'bg-secondary/10 text-secondary',
  primary: 'bg-primary/10 text-primary',
  neutral: 'bg-surface-container text-muted',
}

export function Badge({
  children,
  tone = 'neutral',
  icon,
  className = '',
}: {
  children: ReactNode
  tone?: Tone
  icon?: string
  className?: string
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-label-md font-bold ${TONE[tone]} ${className}`}
    >
      {icon && <Icon name={icon} className="text-[14px]" />}
      {children}
    </span>
  )
}

// Carte KPI (chiffre + icône + ligne de contexte sous un séparateur).
export function StatCard({
  label,
  value,
  unit,
  icon,
  footLeft,
  footRight,
}: {
  label: string
  value: ReactNode
  unit?: string
  icon: string
  footLeft?: ReactNode
  footRight?: ReactNode
}) {
  return (
    <div className="bg-surface p-space-lg rounded-2xl border border-border shadow-sm flex flex-col justify-between hover:border-outline-variant transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex flex-col">
          <span className="text-label-lg font-label-lg text-muted">{label}</span>
          <span className="text-[32px] font-headline-lg text-primary tabular-nums mt-1 leading-none">
            {value}
            {unit && (
              <span className="text-subtitle-md font-semibold text-secondary ml-1">
                {unit}
              </span>
            )}
          </span>
        </div>
        <div className="w-10 h-10 rounded-xl bg-surface-container flex items-center justify-center text-primary">
          <Icon name={icon} className="text-[22px]" />
        </div>
      </div>
      {(footLeft || footRight) && (
        <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-label-md">
          <span className="text-muted">{footLeft}</span>
          {footRight}
        </div>
      )}
    </div>
  )
}

// En-tête de page (titre + sous-titre + actions à droite).
export function PageHeader({
  title,
  subtitle,
  badge,
  actions,
}: {
  title: string
  subtitle?: string
  badge?: ReactNode
  actions?: ReactNode
}) {
  return (
    <section className="flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-headline-lg font-headline-lg text-ink tracking-tight">
            {title}
          </h1>
          {badge}
        </div>
        {subtitle && (
          <p className="text-body-md font-body-md text-muted mt-1">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </section>
  )
}

// Champ texte stylé console.
export function Field({
  label,
  className = '',
  ...rest
}: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className={`block space-y-1.5 ${className}`}>
      <span className="block text-label-lg font-semibold text-ink">{label}</span>
      <input
        className="w-full px-3 py-2.5 text-body-md text-ink placeholder:text-outline bg-white rounded-xl border border-border focus:border-secondary focus:ring-2 focus:ring-secondary/20 outline-none transition-all"
        {...rest}
      />
    </label>
  )
}

// Liste déroulante stylée console.
export function Select({
  label,
  className = '',
  children,
  ...rest
}: { label: string } & React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <label className={`block space-y-1.5 ${className}`}>
      <span className="block text-label-lg font-semibold text-ink">{label}</span>
      <select
        className="w-full px-3 py-2.5 text-body-md text-ink bg-white rounded-xl border border-border focus:border-secondary focus:ring-2 focus:ring-secondary/20 outline-none transition-all"
        {...rest}
      >
        {children}
      </select>
    </label>
  )
}

// Bouton primaire teal (accent Stitch) et variante neutre.
export function Button({
  children,
  variant = 'neutral',
  icon,
  iconRight,
  className = '',
  ...rest
}: {
  children: ReactNode
  variant?: 'primary' | 'neutral' | 'ghost'
  icon?: string
  iconRight?: string
  className?: string
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const base =
    'inline-flex items-center justify-center gap-1.5 rounded-xl font-bold text-label-lg transition-all duration-150 active:scale-95 disabled:opacity-50 disabled:pointer-events-none'
  const styles =
    variant === 'primary'
      ? 'px-4 py-2 bg-secondary-fixed text-ink hover:bg-secondary-fixed-dim shadow-sm'
      : variant === 'ghost'
        ? 'px-3 py-2 text-muted hover:text-ink hover:bg-surface-container'
        : 'px-3.5 py-2 bg-surface text-ink border border-border hover:bg-surface-container shadow-sm'
  return (
    <button className={`${base} ${styles} ${className}`} {...rest}>
      {icon && <Icon name={icon} className="text-[18px]" />}
      {children}
      {iconRight && <Icon name={iconRight} className="text-[18px]" />}
    </button>
  )
}
