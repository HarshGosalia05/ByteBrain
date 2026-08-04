"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { CircleAlert, Info, Lightbulb, TriangleAlert } from "lucide-react"

import type { PerformanceInsight } from "@/lib/faculty-api"
import type { SectionResult } from "@/lib/section-result"

type InsightsResult = SectionResult<{ items: PerformanceInsight[] }>

function severityStyle(severity: PerformanceInsight["severity"]) {
  switch (severity) {
    case "critical":
      return {
        icon: CircleAlert,
        className: "bg-destructive/10 text-destructive ring-destructive/20",
      }
    case "warning":
      return {
        icon: TriangleAlert,
        className: "bg-chart-3/20 text-chart-3 ring-chart-3/25",
      }
    default:
      return {
        icon: Info,
        className: "bg-primary/10 text-primary ring-primary/20",
      }
  }
}

export function InsightsView({ data }: { data: InsightsResult }) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const handleInsightClick = (insight: PerformanceInsight) => {
    if (!insight.subject_id) return
    const params = new URLSearchParams(searchParams.toString())
    params.set("subject_id", insight.subject_id)
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}#students`)
  }

  return (
    <section id="insights" className="flex scroll-mt-6 flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Smart insights</h2>
        <p className="text-sm text-muted-foreground">
          Rule-based observations derived from your data in this scope — not AI.
        </p>
      </div>

      {data.error ? (
        <p className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          Failed to load insights: {data.error}
        </p>
      ) : data.data && data.data.items.length > 0 ? (
        <ul className="grid gap-3">
          {data.data.items.map((insight) => {
            const { icon: Icon, className } = severityStyle(insight.severity)
            return (
              <li key={insight.id}>
                <button
                  type="button"
                  onClick={() => handleInsightClick(insight)}
                  disabled={!insight.subject_id}
                  className="flex w-full items-start gap-3 rounded-xl bg-card p-4 text-left ring-1 ring-foreground/10 transition-colors enabled:hover:bg-muted/40 disabled:cursor-default"
                >
                  <span
                    className={`flex size-8 shrink-0 items-center justify-center rounded-full ring-1 ${className}`}
                  >
                    <Icon className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-foreground">{insight.message}</span>
                    {(insight.subject_code || insight.term_label) && (
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {[insight.subject_code, insight.term_label]
                          .filter(Boolean)
                          .join(" · ")}
                        {insight.subject_id ? " · click to filter" : ""}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      ) : (
        <div className="flex items-center gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-chart-2/15 text-chart-2">
            <Lightbulb className="size-4" />
          </span>
          <p className="text-sm text-muted-foreground">
            All your cohorts are at or above the configured baselines in this scope.
          </p>
        </div>
      )}
    </section>
  )
}
