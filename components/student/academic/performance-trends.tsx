import { ArrowDownRight, ArrowUpRight, Minus, TrendingUp } from "lucide-react"

import type { PerformanceTrends, TrendMovement } from "@/lib/student-api"

import { Badge } from "@/components/ui/badge"

const DIRECTION_META = {
  up: { label: "Improved", icon: ArrowUpRight, tone: "success" as const },
  down: { label: "Declined", icon: ArrowDownRight, tone: "destructive" as const },
  flat: { label: "Steady", icon: Minus, tone: "secondary" as const },
}

const OVERALL_TONE = {
  improving: "success" as const,
  declining: "destructive" as const,
  stable: "secondary" as const,
  insufficient: "muted" as const,
}

function MovementCard({
  label,
  movement,
  decimals,
  suffix,
}: {
  label: string
  movement: TrendMovement
  decimals: number
  suffix?: string
}) {
  if (!movement.available) {
    return (
      <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
          {label}
        </p>
        <p className="mt-2 text-sm text-muted-foreground">Not enough history</p>
      </div>
    )
  }

  const meta =
    DIRECTION_META[(movement.direction ?? "flat") as keyof typeof DIRECTION_META] ??
    DIRECTION_META.flat
  const Icon = meta.icon
  const sign = (movement.delta ?? 0) > 0 ? "+" : ""

  return (
    <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
          {label}
        </p>
        <Badge variant={meta.tone}>
          <Icon className="size-3" />
          {meta.label}
        </Badge>
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">
        {sign}
        {(movement.delta ?? 0).toFixed(decimals)}
        {suffix}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        Semester {movement.previous_semester} → Semester {movement.current_semester}
      </p>
    </div>
  )
}

export function PerformanceTrends({ trends }: { trends: PerformanceTrends }) {
  const { movements, overall_direction, interpretation } = trends
  const overallTone = OVERALL_TONE[overall_direction as keyof typeof OVERALL_TONE] ?? "muted"

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
              <TrendingUp className="size-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">Performance trend</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {interpretation ?? "Not enough semester history to determine a trend."}
              </p>
            </div>
          </div>
          <Badge variant={overallTone}>Overall: {overall_direction}</Badge>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-3">
        <MovementCard label="SGPA" movement={movements.sgpa} decimals={2} />
        <MovementCard
          label="Semester percentage"
          movement={movements.percentage}
          decimals={2}
          suffix="%"
        />
        <MovementCard
          label="Attendance"
          movement={movements.attendance}
          decimals={1}
          suffix="%"
        />
      </div>
    </div>
  )
}
