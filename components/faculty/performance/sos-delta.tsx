import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react"

import { cn } from "@/lib/utils"

function formatDelta(delta: number): string {
  const abs = Number.isInteger(delta) ? Math.abs(delta).toString() : Math.abs(delta).toFixed(1)
  return `${delta > 0 ? "+" : "-"}${abs}`
}

type SoSDeltaProps = {
  delta: number | null
  hasPrevious: boolean
  previousDisplay: string | null
}

export function SoSDelta({ delta, hasPrevious, previousDisplay }: SoSDeltaProps) {
  if (!hasPrevious) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Minus className="size-3.5" />
        No previous term
      </span>
    )
  }
  if (delta === null) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Minus className="size-3.5" />
        No prior data
      </span>
    )
  }
  if (delta === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground tabular-nums">
        <Minus className="size-3.5" />
        ±0 vs {previousDisplay}
      </span>
    )
  }
  const up = delta > 0
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs font-medium tabular-nums",
        up ? "text-chart-2" : "text-destructive",
      )}
    >
      {up ? <ArrowUpRight className="size-3.5" /> : <ArrowDownRight className="size-3.5" />}
      {formatDelta(delta)}
      <span className="text-muted-foreground">vs {previousDisplay}</span>
    </span>
  )
}
