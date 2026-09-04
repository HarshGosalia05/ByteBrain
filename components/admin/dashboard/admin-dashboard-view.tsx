import {
  AlertTriangle,
  Award,
  Building2,
  CalendarCheck,
  GraduationCap,
  Percent,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react"

import type { AdminDashboardData } from "@/lib/admin-api"

import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
import { DonutChart } from "@/components/shared/charts/donut-chart"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"
import { AdminFilterBar } from "@/components/admin/dashboard/admin-filter-bar"
import { DepartmentPerformanceCard } from "@/components/admin/dashboard/department-performance-card"
import { AcademicTrendCard } from "@/components/admin/dashboard/academic-trend-card"

const RISK_COLORS: Record<string, string> = {
  Low: "var(--chart-2)",
  Moderate: "var(--chart-3)",
  High: "var(--chart-4)",
  Critical: "var(--chart-5)",
}

function toFixed(value: number | null, digits = 2): string {
  if (value === null || value === undefined) return "—"
  return value.toFixed(digits)
}

function withSuffix(value: number | null, suffix: string): string {
  if (value === null || value === undefined) return "—"
  return `${value}${suffix}`
}

const INSIGHT_KINDS: Record<string, string> = {
  positive: "border-chart-2/30 bg-chart-2/10",
  warning: "border-chart-3/30 bg-chart-3/10",
  info: "border-border bg-muted/40",
}

function InsightsSection({ insights }: { insights: AdminDashboardData["insights"] }) {
  if (insights.length === 0) return null
  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="mb-4 flex items-center gap-2">
        <Sparkles className="size-4 text-primary" />
        <h2 className="text-sm font-semibold">Quick Insights</h2>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {insights.map((insight) => (
          <div
            key={`${insight.title}-${insight.detail}`}
            className={`rounded-lg border p-3 ${INSIGHT_KINDS[insight.kind] ?? INSIGHT_KINDS.info}`}
          >
            <p className="text-sm font-medium">{insight.title}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{insight.detail}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function RiskDonutCard({ data }: { data: AdminDashboardData }) {
  const slices = data.risk_distribution.map((item) => ({
    name: item.risk_level,
    value: item.count,
    color: RISK_COLORS[item.risk_level] ?? "var(--muted-foreground)",
  }))
  const total = slices.reduce((sum, slice) => sum + slice.value, 0)

  return (
    <ChartCard
      title="Risk Distribution"
      subtitle="Students by risk band from the early-warning risk model"
      status={total > 0 ? "ready" : "empty"}
      emptyIcon={ShieldAlert}
      emptyTitle="No risk data"
      emptyDescription="There are no risk predictions in the current selection."
    >
      <DonutChart
        data={slices}
        height={210}
        centerValue={String(total)}
        centerLabel="Students"
        centerHint={`${data.kpis.at_risk_students} at risk`}
      />
    </ChartCard>
  )
}

function AttendanceDistributionCard({
  data,
}: {
  data: AdminDashboardData["attendance_distribution"]
}) {
  const colors: Record<string, string> = {
    Excellent: "var(--chart-2)",
    Good: "var(--chart-1)",
    Average: "var(--chart-4)",
    Low: "var(--chart-3)",
    Critical: "var(--chart-5)",
  }
  const row: Record<string, string | number> = { label: "Status" }
  for (const item of data) {
    row[item.status] = item.count
  }
  const chartData = [row]

  return (
    <ChartCard
      title="Attendance Distribution"
      subtitle="Subject-level attendance status across the selected scope"
      status={data.length > 0 ? "ready" : "empty"}
      emptyIcon={CalendarCheck}
      emptyTitle="No attendance data"
      emptyDescription="There is no attendance data in the current selection."
    >
      <SubjectBarChart
        data={chartData}
        xKey="label"
        height={240}
        bars={data.map((item) => ({
          dataKey: item.status,
          name: item.status,
          color: colors[item.status] ?? "var(--muted-foreground)",
        }))}
      />
    </ChartCard>
  )
}

function ResultOverviewCard({ data }: { data: AdminDashboardData["result_overview"] }) {
  const colors: Record<string, string> = {
    Pass: "var(--chart-2)",
    Fail: "var(--chart-5)",
    Pending: "var(--chart-3)",
  }
  const row: Record<string, string | number> = { label: "Status" }
  for (const item of data) {
    row[item.status] = item.count
  }
  const chartData = [row]

  return (
    <ChartCard
      title="Result Overview"
      subtitle="Subject results in the selected scope (Pending stays pending)"
      status={data.length > 0 ? "ready" : "empty"}
      emptyIcon={GraduationCap}
      emptyTitle="No result data"
      emptyDescription="There are no subject performance results in the current selection."
    >
      <SubjectBarChart
        data={chartData}
        xKey="label"
        height={220}
        bars={data.map((item) => ({
          dataKey: item.status,
          name: item.status,
          color: colors[item.status] ?? "var(--muted-foreground)",
        }))}
      />
    </ChartCard>
  )
}

export function AdminDashboardView({
  data,
  fetchedAt,
}: {
  data: AdminDashboardData
  fetchedAt: string
}) {
  const { kpis } = data

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Admin Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Institution-level academic, attendance, and risk intelligence from live data.
          </p>
        </div>
      </div>

      <AdminFilterBar filters={data.filters} />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-5">
        <StatCard
          label="Total Students"
          value={String(kpis.total_students)}
          icon={Users}
          tone="primary"
        />
        <StatCard
          label="Total Faculty"
          value={String(kpis.total_faculty)}
          icon={GraduationCap}
          tone="primary"
        />
        <StatCard
          label="Departments"
          value={String(kpis.total_departments)}
          icon={Building2}
          tone="primary"
        />
        <StatCard
          label="Avg SGPA"
          value={toFixed(kpis.avg_sgpa)}
          icon={TrendingUp}
          hint="Semester-scoped"
        />
        <StatCard
          label="Avg CGPA"
          value={toFixed(kpis.avg_cgpa)}
          icon={Award}
        />
        <StatCard
          label="Avg Percentage"
          value={withSuffix(kpis.avg_percentage, "%")}
          icon={Percent}
          hint="Semester-scoped"
        />
        <StatCard
          label="Avg Attendance"
          value={withSuffix(kpis.avg_attendance, "%")}
          icon={CalendarCheck}
          hint="Semester-scoped"
        />
        <StatCard
          label="Total Backlogs"
          value={String(kpis.total_backlogs)}
          icon={AlertTriangle}
          tone="warning"
        />
        <StatCard
          label="At-Risk Students"
          value={String(kpis.at_risk_students)}
          icon={ShieldAlert}
          tone="destructive"
          hint="High + Critical"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <DepartmentPerformanceCard data={data.department_performance} />
        <RiskDonutCard data={data} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <AcademicTrendCard data={data.academic_trend} />
        </div>
        <ResultOverviewCard data={data.result_overview} />
      </div>

      <AttendanceDistributionCard data={data.attendance_distribution} />

      <InsightsSection insights={data.insights} />

      <p className="text-xs text-muted-foreground">
        Data refreshed {fetchedAt ? new Date(fetchedAt).toLocaleString() : "just now"}
      </p>
    </div>
  )
}
