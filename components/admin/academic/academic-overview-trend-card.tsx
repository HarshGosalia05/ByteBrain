"use client"

import * as React from "react"
import { TrendingUp } from "lucide-react"

import type { AcademicTrendPoint } from "@/lib/admin-api"
import { cn } from "@/lib/utils"
import { TrendChart } from "@/components/shared/charts/trend-chart"
import { ChartCard } from "@/components/shared/data/chart-card"

type Metric = "sgpa" | "percentage" | "attendance"

const METRICS: Array<{ key: Metric; label: string }> = [
  { key: "sgpa", label: "SGPA" },
  { key: "percentage", label: "%" },
  { key: "attendance", label: "Attendance" },
]

export function AcademicOverviewTrendCard({ data }: { data: AcademicTrendPoint[] }) {
  const [metric, setMetric] = React.useState<Metric>("sgpa")

  const chartData = data.map((item) => ({
    semester: `Sem ${item.semester}`,
    sgpa: item.avg_sgpa,
    percentage: item.avg_percentage,
    attendance: item.avg_attendance ?? null,
  }))
  const empty = chartData.length === 0

  const series =
    metric === "sgpa"
      ? [{ key: "sgpa", label: "Avg SGPA", color: "var(--chart-4)" }]
      : metric === "percentage"
        ? [{ key: "percentage", label: "Avg %", color: "var(--chart-1)" }]
        : [{ key: "attendance", label: "Avg Attendance %", color: "var(--chart-3)" }]
  const yDomain: [number | "auto", number | "auto"] =
    metric === "sgpa" ? [0, 10] : [0, 100]

  return (
    <ChartCard
      title="Academic Trend"
      subtitle="Semester averages in the selected scope"
      status={empty ? "empty" : "ready"}
      emptyIcon={TrendingUp}
      emptyTitle="No trend data"
      emptyDescription="There is no semester summary data in the current selection."
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
          {METRICS.map((m) => (
            <button
              key={m.key}
              type="button"
              className={cn(
                "h-8 rounded px-2.5 text-sm font-medium transition-colors",
                metric === m.key
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setMetric(m.key)}
              aria-pressed={metric === m.key}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <TrendChart data={chartData} xKey="semester" series={series} height={240} yDomain={yDomain} />
    </ChartCard>
  )
}
