import type { ReactNode } from 'react'

export function Panel({
  title,
  subtitle,
  right,
  children,
  className = '',
  icon,
}: {
  title?: string
  subtitle?: string
  right?: ReactNode
  children: ReactNode
  className?: string
  icon?: ReactNode
}) {
  return (
    <section className={`bg-card rounded-xl border border-border shadow-panel ${className}`}>
      {(title || right) && (
        <header className="flex items-center justify-between px-4 pt-3.5 pb-2">
          <div className="flex items-center gap-2">
            {icon && <span className="text-maroon">{icon}</span>}
            <div>
              <h2 className="text-[13.5px] font-bold text-text leading-tight">{title}</h2>
              {subtitle && <p className="text-[11px] text-muted leading-tight mt-0.5">{subtitle}</p>}
            </div>
          </div>
          {right}
        </header>
      )}
      <div className="px-4 pb-4">{children}</div>
    </section>
  )
}
