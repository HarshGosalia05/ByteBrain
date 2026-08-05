import type { LucideIcon } from "lucide-react"

type PreferenceSectionProps = {
  icon: LucideIcon
  title: string
  description?: string
  action?: React.ReactNode
  children: React.ReactNode
}

export function PreferenceSection({
  icon: Icon,
  title,
  description,
  action,
  children,
}: PreferenceSectionProps) {
  return (
    <section className="rounded-xl bg-card ring-1 ring-foreground/10">
      <div className="flex items-start gap-3 border-b border-border/60 p-5">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">{title}</h2>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}
