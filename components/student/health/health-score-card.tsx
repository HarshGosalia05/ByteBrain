import { Activity, BookOpen, CalendarCheck, TrendingUp } from "lucide-react"

import type { HealthScoreResponse } from "@/lib/student-api"

import { Badge } from "@/components/ui/badge"

const componentMeta = {
  attendance: { label: "Attendance", icon: CalendarCheck },
  performance: { label: "Performance", icon: BookOpen },
  progress: { label: "Progress", icon: TrendingUp },
  consistency: { label: "Consistency", icon: Activity },
} as const

const bandTone = {
  Excellent: "success",
  Good: "success",
  Watch: "warning",
  "Needs Attention": "destructive",
} as const

export function HealthScoreCard({ health }: { health: HealthScoreResponse }) {
  const { available, score, band, components, reasons } = health

  if (!available || score === null) {
    return (
      <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <h2 className="text-sm font-semibold">Academic health score</h2>
        <p className="mt-1 text-xs text-muted-foreground">{reasons[0]}</p>
      </div>
    )
  }

  const tone = band && band in bandTone ? bandTone[band as keyof typeof bandTone] : "default"

  return (
    <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Academic health score</h2>
        <Badge variant={tone}>{band}</Badge>
      </div>

      <div className="mt-3 flex items-end gap-2">
        <p className="text-4xl font-semibold tracking-tight tabular-nums">{score.toFixed(1)}</p>
        <p className="mb-1 text-sm text-muted-foreground">/ 100</p>
      </div>

      <ul className="mt-4 flex flex-col gap-2">
        {Object.entries(componentMeta).map(([key, meta]) => {
          const component = components[key]
          if (!component?.available || component.score === null) return null
          const Icon = meta.icon
          return (
            <li key={key} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-sm text-muted-foreground">
                <Icon className="size-4 shrink-0 text-muted-foreground" />
                {meta.label}
              </span>
              <span className="text-sm font-medium tabular-nums">{component.score.toFixed(1)}</span>
            </li>
          )
        })}
      </ul>

      {reasons.length > 0 && (
        <div className="mt-4 border-t border-border/60 pt-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Why this score</p>
          <ul className="flex flex-col gap-1">
            {reasons.map((reason, index) => (
              <li key={index} className="text-xs leading-5 text-muted-foreground">
                • {reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
