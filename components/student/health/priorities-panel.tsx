import { CircleAlert, CircleCheck, Info } from "lucide-react"

import type { PrioritiesResponse } from "@/lib/student-api"

import { Badge } from "@/components/ui/badge"

const signalTone: Record<string, "destructive" | "warning" | "success"> = {
  attendance: "destructive",
  weak_performance: "warning",
  declining_trend: "warning",
  pending_result: "warning",
  backlog: "warning",
  eligibility_issue: "destructive",
  goal_gap: "success",
}

export function PrioritiesPanel({ priorities }: { priorities: PrioritiesResponse }) {
  const { items } = priorities

  if (items.length === 0) {
    return (
      <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <h2 className="text-sm font-semibold">What should you focus on?</h2>
        <p className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
          <CircleCheck className="size-4 shrink-0 text-chart-2" />
          No pressing signals right now. Keep your current rhythm.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <h2 className="text-sm font-semibold">What should you focus on?</h2>
      <p className="text-xs text-muted-foreground">Ranked by impact</p>

      <ol className="mt-4 flex flex-col gap-3">
        {items.map((item) => (
          <li key={item.rank} className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold tabular-nums">
              {item.rank}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium">{item.title}</p>
                <Badge variant={signalTone[item.signal] ?? "warning"}>
                  {item.metric ?? item.signal.replaceAll("_", " ")}
                </Badge>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">{item.reason}</p>
              <p className="mt-1 flex items-start gap-1 text-xs text-primary">
                <Info className="mt-0.5 size-3 shrink-0" />
                {item.action}
              </p>
            </div>
          </li>
        ))}
      </ol>

      {items.length >= 3 && (
        <p className="mt-3 flex items-center gap-1 text-xs font-medium text-muted-foreground">
          <CircleAlert className="size-3" />
          Focus on one signal at a time before moving to the next.
        </p>
      )}
    </div>
  )
}
