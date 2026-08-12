import {
  AlertTriangle,
  BookOpen,
  Building2,
  CheckCircle2,
  Flame,
  ShieldAlert,
  Siren,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react"

import type {
  EarlyWarningRow,
  RiskIntelligenceData,
  RiskStudentRow,
} from "@/lib/admin-api"

import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
import { DonutChart } from "@/components/shared/charts/donut-chart"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"
import { RiskFilterBar } from "@/components/admin/risk/risk-filter-bar"

const RISK_COLORS: Record<string, string> = {
  Low: "var(--chart-2)",
  Moderate: "var(--chart-3)",
  High: "var(--chart-4)",
  Critical: "var(--chart-5)",
}

const RISK_SERIES = [
  { dataKey: "Low", name: "Low", color: RISK_COLORS.Low },
  { dataKey: "Moderate", name: "Moderate", color: RISK_COLORS.Moderate },
  { dataKey: "High", name: "High", color: RISK_COLORS.High },
  { dataKey: "Critical", name: "Critical", color: RISK_COLORS.Critical },
]

const BADGE_STYLES: Record<string, string> = {
  Low: "bg-chart-2/15 text-chart-2",
  Moderate: "bg-chart-3/20 text-chart-3",
  High: "bg-chart-4/20 text-chart-4",
  Critical: "bg-destructive/10 text-destructive",
}

function toFixed(value: number | null, digits = 2): string {
  if (value === null || value === undefined) return "—"
  return value.toFixed(digits)
}

function withSuffix(value: number | null, suffix: string): string {
  if (value === null || value === undefined) return "—"
  return `${toFixed(value)}${suffix}`
}

function RiskBadge({ level }: { level: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
        BADGE_STYLES[level] ?? "bg-muted text-muted-foreground"
      }`}
    >
      {level}
    </span>
  )
}

function RiskDistributionCard({ data }: { data: RiskIntelligenceData["distribution"] }) {
  const slices = data.map((item) => ({
    name: item.risk_level,
    value: item.count,
    color: RISK_COLORS[item.risk_level] ?? "var(--muted-foreground)",
  }))
  const total = slices.reduce((sum, slice) => sum + slice.value, 0)
  const atRisk = slices
    .filter((slice) => slice.name === "High" || slice.name === "Critical")
    .reduce((sum, slice) => sum + slice.value, 0)

  return (
    <ChartCard
      title="Risk Distribution"
      subtitle="Students by risk band from stored risk predictions"
      status={total > 0 ? "ready" : "empty"}
      emptyIcon={ShieldAlert}
      emptyTitle="No risk data"
      emptyDescription="There are no risk predictions in the current selection."
    >
      <DonutChart
        data={slices}
        height={210}
        centerValue={String(total)}
        centerLabel="Predicted"
        centerHint={`${atRisk} at risk`}
      />
    </ChartCard>
  )
}

function bandCounts(
  distribution: { risk_level: string; count: number }[],
): Record<string, number> {
  return distribution.reduce<Record<string, number>>((acc, item) => {
    acc[item.risk_level] = item.count
    return acc
  }, {})
}

function RiskByDepartmentCard({
  data,
}: {
  data: RiskIntelligenceData["by_department"]
}) {
  const chartData = data.map((item) => {
    const counts = bandCounts(item.distribution)
    return {
      department: item.department_name,
      Low: counts.Low ?? 0,
      Moderate: counts.Moderate ?? 0,
      High: counts.High ?? 0,
      Critical: counts.Critical ?? 0,
    }
  })

  return (
    <ChartCard
      title="Risk by Department"
      subtitle="Students by risk band per department"
      status={chartData.length > 0 ? "ready" : "empty"}
      emptyIcon={Building2}
      emptyTitle="No department data"
      emptyDescription="There are no departments in the current selection."
    >
      <SubjectBarChart data={chartData} xKey="department" height={240} bars={RISK_SERIES} />
    </ChartCard>
  )
}

function RiskBySemesterCard({
  data,
}: {
  data: RiskIntelligenceData["by_semester"]
}) {
  const chartData = data.map((item) => {
    const counts = bandCounts(item.distribution)
    return {
      semester: `Sem ${item.semester}`,
      Low: counts.Low ?? 0,
      Moderate: counts.Moderate ?? 0,
      High: counts.High ?? 0,
      Critical: counts.Critical ?? 0,
    }
  })

  return (
    <ChartCard
      title="Risk by Semester"
      subtitle="Students by risk band per semester"
      status={chartData.length > 0 ? "ready" : "empty"}
      emptyIcon={TrendingUp}
      emptyTitle="No semester data"
      emptyDescription="There are no semesters in the current selection."
    >
      <SubjectBarChart data={chartData} xKey="semester" height={240} bars={RISK_SERIES} />
    </ChartCard>
  )
}

function AtRiskTable({
  rows,
  total,
}: {
  rows: RiskStudentRow[]
  total: number
}) {
  return (
    <ChartCard
      title="At-Risk Students"
      subtitle="Students with a stored risk prediction, sorted by severity"
      status={rows.length > 0 ? "ready" : "empty"}
      emptyIcon={Users}
      emptyTitle="No at-risk students"
      emptyDescription="No students match the current filters."
      exportFileName="admin_at_risk_students.csv"
      exportColumns={[
        { key: "student_id", label: "Student ID" },
        { key: "student_name", label: "Student" },
        { key: "enrollment_no", label: "Enrollment" },
        { key: "department_name", label: "Department" },
        { key: "semester", label: "Semester" },
        { key: "academic_year", label: "Academic Year" },
        { key: "attendance", label: "Attendance" },
        { key: "percentage", label: "Percentage" },
        { key: "backlogs", label: "Backlogs" },
        { key: "academic_standing", label: "Academic Standing" },
        { key: "risk", label: "Risk" },
      ]}
      exportRows={rows as unknown as Array<Record<string, unknown>>}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-190 text-left text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground uppercase">
              <th className="py-2 pr-4 font-medium">Student</th>
              <th className="py-2 pr-4 text-right font-medium">Enrollment</th>
              <th className="py-2 pr-4 font-medium">Department</th>
              <th className="py-2 pr-4 text-right font-medium">Sem</th>
              <th className="py-2 pr-4 text-right font-medium">Attendance</th>
              <th className="py-2 pr-4 text-right font-medium">Percentage</th>
              <th className="py-2 pr-4 text-right font-medium">Backlogs</th>
              <th className="py-2 pr-4 font-medium">Standing</th>
              <th className="py-2 text-right font-medium">Risk</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.student_id} className="border-b last:border-0">
                <td className="py-2.5 pr-4">
                  <p className="max-w-52 truncate font-medium">{row.student_name}</p>
                  <p className="text-xs text-muted-foreground">{row.student_id}</p>
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{row.enrollment_no}</td>
                <td className="py-2.5 pr-4 text-xs">{row.department_name}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">
                  {row.semester ?? "—"}
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums">
                  {withSuffix(row.attendance, "%")}
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums">
                  {withSuffix(row.percentage, "%")}
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums">
                  {row.backlogs ?? "—"}
                </td>
                <td className="py-2.5 pr-4 text-xs">{row.academic_standing ?? "—"}</td>
                <td className="py-2.5 text-right">
                  <RiskBadge level={row.risk} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        {total} predicted student{total === 1 ? "" : "s"} in the selected scope
      </p>
    </ChartCard>
  )
}

function EarlyWarningTable({
  rows,
}: {
  rows: EarlyWarningRow[]
}) {
  return (
    <ChartCard
      title="Early Warning Center"
      subtitle="High/Critical students with deterministic reasons and recommended actions"
      status={rows.length > 0 ? "ready" : "empty"}
      emptyIcon={Sparkles}
      emptyTitle="No early warnings"
      emptyDescription="No High/Critical students in the current selection."
      exportFileName="admin_early_warning.csv"
      exportColumns={[
        { key: "student_id", label: "Student ID" },
        { key: "student_name", label: "Student" },
        { key: "enrollment_no", label: "Enrollment" },
        { key: "department_name", label: "Department" },
        { key: "semester", label: "Semester" },
        { key: "severity", label: "Severity" },
        { key: "primary_concern", label: "Primary Risk" },
        { key: "supporting_signals", label: "Supporting Signals" },
        { key: "recommended_action", label: "Recommended Action" },
      ]}
      exportRows={rows.map((row) => ({
        ...row,
        supporting_signals: row.supporting_signals.join(", "),
      }))}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-200 text-left text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground uppercase">
              <th className="py-2 pr-4 font-medium">Student</th>
              <th className="py-2 pr-4 text-right font-medium">Severity</th>
              <th className="py-2 pr-4 font-medium">Primary Risk</th>
              <th className="py-2 pr-4 font-medium">Supporting Signals</th>
              <th className="py-2 text-right font-medium">Recommended Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.student_id} className="border-b last:border-0 align-top">
                <td className="py-2.5 pr-4">
                  <p className="max-w-44 truncate font-medium">{row.student_name}</p>
                  <p className="text-xs text-muted-foreground">{row.student_id}</p>
                </td>
                <td className="py-2.5 pr-4 text-right">
                  <RiskBadge level={row.severity} />
                </td>
                <td className="py-2.5 pr-4 text-xs">{row.primary_concern ?? "—"}</td>
                <td className="py-2.5 pr-4">
                  <div className="flex flex-wrap gap-1">
                    {row.supporting_signals.length > 0 ? (
                      row.supporting_signals.map((signal) => (
                        <span
                          key={signal}
                          className="inline-flex items-center rounded-md bg-muted px-1.5 py-0.5 text-[0.6875rem] font-medium text-muted-foreground"
                        >
                          {signal}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </div>
                </td>
                <td className="py-2.5 text-right">
                  <span className="text-xs font-medium text-primary">
                    {row.recommended_action ?? "—"}
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

export function RiskIntelligenceView({
  data,
  fetchedAt,
}: {
  data: RiskIntelligenceData
  fetchedAt: string
}) {
  const { kpis } = data

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Risk &amp; Early Warning</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Risk-band distribution, at-risk students and deterministic early-warning signals.
          </p>
        </div>
      </div>

      <RiskFilterBar filters={data.filters} />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-5">
        <StatCard
          label="At Risk"
          value={String(kpis.at_risk)}
          icon={ShieldAlert}
          tone="destructive"
          hint="High + Critical"
        />
        <StatCard label="Low" value={String(kpis.low)} icon={CheckCircle2} tone="success" />
        <StatCard
          label="Moderate"
          value={String(kpis.moderate)}
          icon={AlertTriangle}
          tone="warning"
        />
        <StatCard label="High" value={String(kpis.high)} icon={Flame} tone="warning" />
        <StatCard
          label="Critical"
          value={String(kpis.critical)}
          icon={Siren}
          tone="destructive"
          hint={`${kpis.total_predicted} predicted total`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <RiskDistributionCard data={data.distribution} />
        <RiskByDepartmentCard data={data.by_department} />
        <RiskBySemesterCard data={data.by_semester} />
      </div>

      <AtRiskTable rows={data.students} total={data.students_total} />

      <EarlyWarningTable rows={data.early_warning} />

      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span>
          Data refreshed {fetchedAt ? new Date(fetchedAt).toLocaleString() : "just now"}
        </span>
        <span className="flex items-center gap-1">
          <BookOpen className="size-3.5" /> Risk bands come from stored risk predictions (no ML)
        </span>
      </div>
    </div>
  )
}
