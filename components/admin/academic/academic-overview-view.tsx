import {
  Award,
  CalendarCheck,
  BookOpen,
  ClipboardCheck,
  Percent,
  TrendingUp,
} from "lucide-react"

import type { AcademicOverviewData } from "@/lib/admin-api"

import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"
import { AdminFilterBar } from "@/components/admin/dashboard/admin-filter-bar"
import { AcademicOverviewTrendCard } from "@/components/admin/academic/academic-overview-trend-card"

const GRADE_COLORS: Record<string, string> = {
  O: "var(--chart-2)",
  "A+": "var(--chart-1)",
  A: "var(--chart-4)",
  "B+": "var(--chart-3)",
  B: "var(--chart-5)",
  C: "var(--muted-foreground)",
  F: "var(--destructive)",
  Pending: "var(--border)",
}

function toFixed(value: number | null, digits = 2): string {
  if (value === null || value === undefined) return "—"
  return value.toFixed(digits)
}

function withSuffix(value: number | null, suffix: string): string {
  if (value === null || value === undefined) return "—"
  return `${toFixed(value)}${suffix}`
}

function PassRateTrendCard({
  data,
}: {
  data: AcademicOverviewData["pass_rate_trend"]
}) {
  const chartData = data.map((item) => ({
    semester: `Sem ${item.semester}`,
    pass_rate: item.pass_rate,
  }))

  return (
    <ChartCard
      title="Pass Rate Trend"
      subtitle="Completed subject results per semester (Pending excluded)"
      status={chartData.length > 0 ? "ready" : "empty"}
      emptyIcon={ClipboardCheck}
      emptyTitle="No pass-rate data"
      emptyDescription="There are no completed results in the current selection."
    >
      <SubjectBarChart
        data={chartData}
        xKey="semester"
        height={240}
        bars={[{ dataKey: "pass_rate", name: "Pass %", color: "var(--chart-2)" }]}
      />
    </ChartCard>
  )
}

function GradeDistributionCard({
  data,
}: {
  data: AcademicOverviewData["grade_distribution"]
}) {
  const chartData = data.map((item) => ({
    grade: item.grade,
    count: item.count,
  }))
  const total = chartData.reduce((sum, item) => sum + item.count, 0)

  return (
    <ChartCard
      title="Grade Distribution"
      subtitle="Subject grades in the selected scope (NULL grades stay Pending)"
      status={chartData.length > 0 ? "ready" : "empty"}
      emptyIcon={Award}
      emptyTitle="No grade data"
      emptyDescription="There are no graded subjects in the current selection."
    >
      <SubjectBarChart
        data={chartData}
        xKey="grade"
        dataKey="count"
        height={240}
        bars={chartData.map((item) => ({
          dataKey: "count",
          name: `${item.grade}${item.grade === "Pending" ? ` (${item.count})` : ""}`,
          color: GRADE_COLORS[item.grade] ?? "var(--muted-foreground)",
        }))}
      />
      <p className="mt-2 text-right text-xs text-muted-foreground">
        {total} graded results
      </p>
    </ChartCard>
  )
}

export function AcademicOverviewView({
  data,
  fetchedAt,
}: {
  data: AcademicOverviewData
  fetchedAt: string
}) {
  const { kpis } = data

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Academic Overview</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Institution academic performance from live semester and subject data.
          </p>
        </div>
      </div>

      <AdminFilterBar filters={data.filters} />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Avg SGPA" value={toFixed(kpis.avg_sgpa)} icon={TrendingUp} />
        <StatCard
          label="Avg Percentage"
          value={withSuffix(kpis.avg_percentage, "%")}
          icon={Percent}
        />
        <StatCard
          label="Pass Rate"
          value={withSuffix(kpis.pass_rate, "%")}
          icon={ClipboardCheck}
          hint="Pending excluded"
          tone="success"
        />
        <StatCard
          label="Avg Attendance"
          value={withSuffix(kpis.avg_attendance, "%")}
          icon={CalendarCheck}
        />
        <StatCard label="Total Backlogs" value={String(kpis.total_backlogs)} icon={BookOpen} />
        <StatCard
          label="Credits Earned"
          value={String(kpis.credits_earned)}
          icon={Award}
          hint="Passed credits"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <AcademicOverviewTrendCard data={data.trend} />
        </div>
        <PassRateTrendCard data={data.pass_rate_trend} />
      </div>

      <GradeDistributionCard data={data.grade_distribution} />

      <p className="text-xs text-muted-foreground">
        Data refreshed {fetchedAt ? new Date(fetchedAt).toLocaleString() : "just now"}
      </p>
    </div>
  )
}
