"use client"

import { Sparkles } from "lucide-react"
import type { GroundedExecutiveInsight } from "@/lib/admin-api"
import { ChartCard } from "@/components/shared/data/chart-card"

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-destructive/10 text-destructive border-destructive/20",
  medium: "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400",
  low: "bg-blue-500/10 text-blue-600 border-blue-500/20 dark:text-blue-400",
}

export function GroundedInsightsCard({
  insights,
}: {
  insights: GroundedExecutiveInsight[]
}) {
  return (
    <ChartCard
      title="Grounded Administrative Insights & Decision Support"
      subtitle="Deterministic, rule-backed executive recommendations derived from M1-M4 outputs"
      status={insights.length > 0 ? "ready" : "empty"}
      emptyIcon={Sparkles}
      emptyTitle="No Executive Insights"
      emptyDescription="No administrative insights generated for current selection."
    >
      <div className="grid gap-4 md:grid-cols-2">
        {insights.map((item, idx) => (
          <div
            key={idx}
            className="flex flex-col justify-between rounded-xl border border-border p-4 transition-all hover:border-primary/40"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {item.category}
                </span>
                <span
                  className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${
                    PRIORITY_STYLES[item.priority] ?? "bg-muted text-muted-foreground"
                  }`}
                >
                  {item.priority.toUpperCase()} PRIORITY
                </span>
              </div>
              <h3 className="font-semibold text-sm text-foreground">{item.title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{item.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </ChartCard>
  )
}
