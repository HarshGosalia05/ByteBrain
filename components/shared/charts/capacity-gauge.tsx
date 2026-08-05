import { Badge } from "@/components/ui/badge"

export type CapacityGaugeProps = {
  utilizationPct: number
  actualWeeklyHours: number
  capacityWeeklyHours: number
  remainingCapacity: number
  overloadThreshold: number
  underutilizedThreshold: number
  band: string
  reason: string
}

const ARC_LENGTH = 314.16

function toneColor(utilization: number, overloadThreshold: number, underutilizedThreshold: number) {
  if (utilization >= overloadThreshold * 100) return "var(--chart-5)"
  if (utilization < underutilizedThreshold * 100) return "var(--chart-3)"
  return "var(--chart-2)"
}

export function CapacityGauge({
  utilizationPct,
  actualWeeklyHours,
  capacityWeeklyHours,
  remainingCapacity,
  overloadThreshold,
  underutilizedThreshold,
  band,
  reason,
}: CapacityGaugeProps) {
  const clamped = Math.min(100, Math.max(0, utilizationPct))
  const color = toneColor(utilizationPct, overloadThreshold, underutilizedThreshold)
  const offset = ARC_LENGTH * (1 - clamped / 100)

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative">
        <svg viewBox="0 0 240 138" className="w-full max-w-64" role="img" aria-label={`Capacity utilization ${utilizationPct.toFixed(1)}%`}>
          <path
            d="M 20 120 A 100 100 0 0 1 220 120"
            fill="none"
            stroke="var(--muted)"
            strokeWidth={14}
            strokeLinecap="round"
            strokeDasharray={ARC_LENGTH}
          />
          <path
            d="M 20 120 A 100 100 0 0 1 220 120"
            fill="none"
            stroke={color}
            strokeWidth={14}
            strokeLinecap="round"
            strokeDasharray={ARC_LENGTH}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 600ms ease-out" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
          <span className="text-3xl font-semibold tabular-nums">{utilizationPct.toFixed(1)}%</span>
          <span className="text-xs text-muted-foreground">
            of {capacityWeeklyHours}h weekly capacity
          </span>
        </div>
      </div>
      <div className="flex flex-col items-center gap-1 text-center">
        <Badge variant={band === "Overloaded" ? "destructive" : band === "Underutilized" ? "warning" : "success"}>
          {band}
        </Badge>
        <p className="text-xs text-muted-foreground">
          {actualWeeklyHours.toFixed(1)}h used · {remainingCapacity.toFixed(1)}h remaining
        </p>
        {reason && <p className="max-w-64 text-xs text-muted-foreground">{reason}</p>}
      </div>
    </div>
  )
}
