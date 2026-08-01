import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

type StatCardProps = React.ComponentProps<"div"> & {
  label: string
  value: string
  icon: LucideIcon
  hint?: string
}

export function StatCard({ label, value, icon: Icon, hint, className, ...props }: StatCardProps) {
  return (
    <div
      className={cn(
        "flex items-start justify-between gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10",
        className,
      )}
      {...props}
    >
      <div className="flex min-w-0 flex-col gap-1">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tracking-tight">{value}</p>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
        <Icon className="size-4 text-primary" />
      </div>
    </div>
  )
}
