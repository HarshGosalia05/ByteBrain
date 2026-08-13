import type { LucideIcon } from "lucide-react"

type ModelCardProps = {
  id: string
  icon: LucideIcon
  title: string
  subtitle?: string
  badge?: React.ReactNode
  children: React.ReactNode
}

export function ModelCard({
  id,
  icon: Icon,
  title,
  subtitle,
  badge,
  children,
}: ModelCardProps) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      className="rounded-xl bg-card p-4 ring-1 ring-foreground/10 sm:p-5"
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Icon className="size-4" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h2 id={`${id}-heading`} className="text-sm font-semibold">
              {title}
            </h2>
            {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
          </div>
        </div>
        {badge}
      </header>
      <div className="mt-4">{children}</div>
    </section>
  )
}
