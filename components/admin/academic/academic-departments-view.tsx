import {
  Award,
  Building2,
  ShieldAlert,
  TrendingUp,
} from "lucide-react"

import type { DepartmentAnalyticsData } from "@/lib/admin-api"

import { ChartCard } from "@/components/shared/data/chart-card"
import { DonutChart } from "@/components/shared/charts/donut-chart"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"
import { AdminFilterBar } from "@/components/admin/dashboard/admin-filter-bar"

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
  return `${toFixed(value)}${suffix}`
}

function MetricCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
        {label}
      </p>
      <p className="text-lg font-semibold tracking-tight tabular-nums">{value}</p>
    </div>
  )
}

function DepartmentSummaryCard({
  department,
}: {
  department: DepartmentAnalyticsData["departments"][number]
}) {
  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="mb-4 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Building2 className="size-4 shrink-0 text-primary" />
          <h2 className="truncate text-sm font-semibold">{department.department_name}</h2>
        </div>
        {department.department_short_name && (
          <span className="shrink-0 rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
            {department.department_short_name}
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MetricCell label="Students" value={String(department.total_students)} />
        <MetricCell label="Faculty" value={String(department.total_faculty)} />
        <MetricCell label="Avg SGPA" value={toFixed(department.avg_sgpa)} />
        <MetricCell label="Avg %" value={withSuffix(department.avg_percentage, "%")} />
        <MetricCell
          label="Attendance"
          value={withSuffix(department.avg_attendance, "%")}
        />
        <MetricCell label="Backlogs" value={String(department.total_backlogs)} />
        <MetricCell label="Pass Rate" value={withSuffix(department.pass_rate, "%")} />
        <MetricCell
          label="At Risk"
          value={String(department.at_risk_students)}
        />
      </div>
    </section>
  )
}

function ComparisonChartCard({
  title,
  subtitle,
  chartData,
  color,
}: {
  title: string
  subtitle: string
  chartData: Array<{ department: string; value: number | null }>
  color: string
}) {
  return (
    <ChartCard
      title={title}
      subtitle={subtitle}
      status={chartData.length > 0 ? "ready" : "empty"}
      emptyIcon={TrendingUp}
      emptyTitle="No comparison data"
      emptyDescription="There are no departments in the current selection."
    >
      <SubjectBarChart
        data={chartData}
        xKey="department"
        height={240}
        bars={[{ dataKey: "value", name: title, color }]}
      />
    </ChartCard>
  )
}

function RiskComparisonCard({
  departments,
}: {
  departments: DepartmentAnalyticsData["departments"]
}) {
  return (
    <ChartCard
      title="Risk Distribution"
      subtitle="Students by risk band per department"
      status={departments.length > 0 ? "ready" : "empty"}
      emptyIcon={ShieldAlert}
      emptyTitle="No risk data"
      emptyDescription="There are no departments in the current selection."
    >
      <div className="grid gap-6 sm:grid-cols-2">
        {departments.map((department) => {
          const slices = department.risk_distribution.map((item) => ({
            name: item.risk_level,
            value: item.count,
            color: RISK_COLORS[item.risk_level] ?? "var(--muted-foreground)",
          }))
          return (
            <div key={department.department_code}>
              <p className="mb-2 text-center text-xs font-semibold">
                {department.department_short_name || department.department_name}
              </p>
              <DonutChart
                data={slices}
                height={190}
                centerValue={String(
                  department.risk_distribution.reduce((sum, item) => sum + item.count, 0),
                )}
                centerLabel="Students"
                centerHint={`${department.at_risk_students} at risk`}
              />
            </div>
          )
        })}
      </div>
    </ChartCard>
  )
}

function RankingTable({ data }: { data: DepartmentAnalyticsData["ranking"] }) {
  return (
    <ChartCard
      title="Department Ranking"
      subtitle="Ranked by average percentage (deterministic, tie-broken by code)"
      status={data.length > 0 ? "ready" : "empty"}
      emptyIcon={Award}
      emptyTitle="No ranking data"
      emptyDescription="There are no departments in the current selection."
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-130 text-left text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground uppercase">
              <th className="py-2 pr-4 font-medium">Rank</th>
              <th className="py-2 pr-4 font-medium">Department</th>
              <th className="py-2 pr-4 text-right font-medium">Students</th>
              <th className="py-2 pr-4 text-right font-medium">SGPA</th>
              <th className="py-2 pr-4 text-right font-medium">Percentage</th>
              <th className="py-2 pr-4 text-right font-medium">Attendance</th>
              <th className="py-2 text-right font-medium">Risk</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.department_code} className="border-b last:border-0">
                <td className="py-2.5 pr-4">
                  <span className="flex size-6 items-center justify-center rounded-full bg-muted text-xs font-semibold">
                    {row.rank}
                  </span>
                </td>
                <td className="py-2.5 pr-4 font-medium">{row.department_name}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">
                  {row.total_students}
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{toFixed(row.avg_sgpa)}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">
                  {withSuffix(row.avg_percentage, "%")}
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums">
                  {withSuffix(row.avg_attendance, "%")}
                </td>
                <td className="py-2.5 text-right">
                  <span className="inline-flex items-center gap-1 font-medium tabular-nums text-destructive">
                    <ShieldAlert className="size-3.5" />
                    {row.at_risk_students}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartCard>
  )
}

export function AcademicDepartmentsView({
  data,
  fetchedAt,
}: {
  data: DepartmentAnalyticsData
  fetchedAt: string
}) {
  const percentageData = data.departments.map((d) => ({
    department: d.department_short_name || d.department_name,
    value: d.avg_percentage,
  }))
  const attendanceData = data.departments.map((d) => ({
    department: d.department_short_name || d.department_name,
    value: d.avg_attendance,
  }))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Department Analytics</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Compare and rank departments on real academic and attendance metrics.
          </p>
        </div>
      </div>

      <AdminFilterBar filters={data.filters} />

      <div className="flex flex-col gap-4">
        {data.departments.map((department) => (
          <DepartmentSummaryCard key={department.department_code} department={department} />
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ComparisonChartCard
          title="Average Percentage"
          subtitle="Per department in the selected scope"
          chartData={percentageData}
          color="var(--chart-1)"
        />
        <ComparisonChartCard
          title="Average Attendance"
          subtitle="Per department in the selected scope"
          chartData={attendanceData}
          color="var(--chart-3)"
        />
        <RiskComparisonCard departments={data.departments} />
      </div>

      <RankingTable data={data.ranking} />

      <p className="text-xs text-muted-foreground">
        Data refreshed {fetchedAt ? new Date(fetchedAt).toLocaleString() : "just now"}
      </p>
    </div>
  )
}
