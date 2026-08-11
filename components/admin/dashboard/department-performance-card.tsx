"use client"

import * as React from "react"
import { Building2 } from "lucide-react"

import type { DepartmentPerformanceItem } from "@/lib/admin-api"
import { cn } from "@/lib/utils"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"
import { ChartCard } from "@/components/shared/data/chart-card"

type Metric = "percentage" | "sgpa"

export function DepartmentPerformanceCard({
  data,
}: {
  data: DepartmentPerformanceItem[]
}) {
  const [metric, setMetric] = React.useState<Metric>("percentage")

  const usable = data.filter((item) => item.percentage !== null || item.sgpa !== null)
  const chartData = usable.map((item) => ({
    name: item.department_name,
    percentage: item.percentage,
    sgpa: item.sgpa,
  }))
  const empty = chartData.length === 0

  return (
    <ChartCard
      title="Department Performance"
      subtitle={
        metric === "percentage"
          ? "Average percentage across departments in the selected scope"
          : "Average SGPA across departments in the selected scope"
      }
      status={empty ? "empty" : "ready"}
      emptyIcon={Building2}
      emptyTitle="No department performance data"
      emptyDescription="There is no semester summary data in the current selection."
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
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
        </div>
      </div>
      <SubjectBarChart
        data={chartData}
        xKey="name"
        dataKey={metric}
        color={metric === "percentage" ? "var(--chart-1)" : "var(--chart-4)"}
        height={260}
      />
    </ChartCard>
  )
}
