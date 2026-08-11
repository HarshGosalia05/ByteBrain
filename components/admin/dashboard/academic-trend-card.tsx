"use client"

import * as React from "react"
import { TrendingUp } from "lucide-react"

import type { AcademicTrendPoint } from "@/lib/admin-api"
import { cn } from "@/lib/utils"
import { TrendChart } from "@/components/shared/charts/trend-chart"
import { ChartCard } from "@/components/shared/data/chart-card"

type Metric = "sgpa" | "percentage"

export function AcademicTrendCard({
  data,
}: {
  data: AcademicTrendPoint[]
}) {
  const [metric, setMetric] = React.useState<Metric>("sgpa")

  const usable = data.filter((item) => item.avg_sgpa !== null || item.avg_percentage !== null)
  const chartData = usable.map((item) => ({
    semester: `Sem ${item.semester}`,
    sgpa: item.avg_sgpa,
    percentage: item.avg_percentage,
  }))
  const empty = chartData.length === 0

  const series =
    metric === "sgpa"
      ? [{ key: "sgpa", label: "Avg SGPA", color: "var(--chart-4)" }]
      : [{ key: "percentage", label: "Avg %", color: "var(--chart-1)" }]
  const yDomain: [number | "auto", number | "auto"] =
    metric === "sgpa" ? [0, 10] : [0, 100]

  return (
    <ChartCard
      title="Academic Trend"
      subtitle="Average SGPA / percentage across semesters in the selected scope"
      status={empty ? "empty" : "ready"}
      emptyIcon={TrendingUp}
      emptyTitle="No trend data"
      emptyDescription="There is no semester summary data in the current selection."
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
          <button
            type="button"
            className={cn(
              "h-8 rounded px-2.5 text-sm font-medium transition-colors",
              metric === "sgpa"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
            onClick={() => setMetric("sgpa")}
            aria-pressed={metric === "sgpa"}
          >
            SGPA
          </button>
          <button
            type="button"
            className={cn(
              "h-8 rounded px-2.5 text-sm font-medium transition-colors",
              metric === "percentage"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
            onClick={() => setMetric("percentage")}
            aria-pressed={metric === "percentage"}
          >
            %
          </button>
        </div>
      </div>
      <TrendChart data={chartData} xKey="semester" series={series} height={240} yDomain={yDomain} />
    </ChartCard>
  )
}
