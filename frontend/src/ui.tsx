import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'

export function Monogram() {
  return <span className="monogram" aria-hidden="true">WS</span>
}

// Logo officiel WaSalaire (charte v1.1). `variant` : couleur (sur fond clair) ou blanc (sur fond indigo).
export function Brand({ height = 26, variant = 'couleur' }: { height?: number; variant?: 'couleur' | 'blanc' }) {
  return <img src={`/logo_${variant}.png`} alt="WaSalaire" height={height} style={{ display: 'block', height }} />
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'dark' | 'ghost'
  block?: boolean
  children: ReactNode
}
export function Button({ variant = 'primary', block, children, className, ...rest }: BtnProps) {
  return (
    <button className={`btn btn-${variant}${block ? ' btn-block' : ''}${className ? ' ' + className : ''}`} {...rest}>
      {children}
    </button>
  )
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & { label: string }
export function Field({ label, ...rest }: FieldProps) {
  return (
    <div className="field">
      <label>{label}</label>
      <input {...rest} />
    </div>
  )
}

export function Spinner() {
  return <span className="spinner" role="status" aria-label="Chargement" />
}
