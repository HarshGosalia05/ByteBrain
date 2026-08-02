import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

const toneStyles = {
  primary: "bg-primary/10 text-primary",
  success: "bg-chart-2/15 text-chart-2",
  warning: "bg-chart-3/20 text-chart-3",
  destructive: "bg-destructive/10 text-destructive",
} as const

export type StatCardTone = keyof typeof toneStyles

type StatCardProps = React.ComponentProps<"div"> & {
  label: string
  value: string
  icon: LucideIcon
  hint?: string
  tone?: StatCardTone
}

export function StatCard({
  label,
  value,
  icon: Icon,
  hint,
  tone = "primary",
  className,
  ...props
}: StatCardProps) {
  return (
    <div
      className={cn(
        "flex items-start justify-between gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10 transition-colors hover:bg-muted/40",
        className,
      )}
      {...props}
    >
      <div className="flex min-w-0 flex-col gap-1">
        <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
          {label}
        </p>
        <p className="text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      <div
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-full",
          toneStyles[tone],
        )}
      >
        <Icon className="size-4" />
      </div>
    </div>
  )
}
