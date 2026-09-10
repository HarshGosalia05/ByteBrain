import {
  AlertTriangle,
  BookOpen,
  CalendarCheck,
  CheckCircle2,
  ShieldAlert,
  TrendingUp,
  Users,
  XCircle,
} from "lucide-react"

import type {
  AttendanceIntelligenceData,
  SubjectAttendanceRow,
} from "@/lib/admin-api"

import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"
import { AttendanceFilterBar } from "@/components/admin/attendance/attendance-filter-bar"
import { ShortageStudentsGrouped } from "@/components/admin/attendance/shortage-students-grouped"

const ATTENDANCE_COLORS: Record<string, string> = {
  Excellent: "var(--chart-2)",
  Good: "var(--chart-1)",
  Average: "var(--chart-4)",
  Low: "var(--chart-3)",
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

function AttendanceByDepartmentCard({
  data,
}: {
  data: AttendanceIntelligenceData["by_department"]
}) {
  const chartData = data.map((item) => ({
    department: item.department_name,
    value: item.avg_attendance,
  }))

  return (
    <ChartCard
      title="Attendance by Department"
      subtitle="Average attendance per department in the selected scope"
      status={chartData.length > 0 ? "ready" : "empty"}
      emptyIcon={TrendingUp}
      emptyTitle="No department data"
      emptyDescription="There are no attendance records in the current selection."
    >
      <SubjectBarChart
        data={chartData}
        xKey="department"
        height={240}
        bars={[{ dataKey: "value", name: "Avg %", color: "var(--chart-1)" }]}
      />
    </ChartCard>
  )
}

function AttendanceBySemesterCard({
  data,
}: {
  data: AttendanceIntelligenceData["by_semester"]
}) {
  const chartData = data.map((item) => ({
    semester: `Sem ${item.semester}`,
    value: item.avg_attendance,
  }))

  return (
    <ChartCard
      title="Attendance by Semester"
      subtitle="Average attendance per semester (numeric order)"
      status={chartData.length > 0 ? "ready" : "empty"}
      emptyIcon={TrendingUp}
      emptyTitle="No semester data"
      emptyDescription="There are no attendance records in the current selection."
    >
      <SubjectBarChart
        data={chartData}
        xKey="semester"
        height={240}
        bars={[{ dataKey: "value", name: "Avg %", color: "var(--chart-2)" }]}
      />
    </ChartCard>
  )
}

function AttendanceDistributionCard({
  data,
}: {
  data: AttendanceIntelligenceData["distribution"]
}) {
  const row: Record<string, string | number> = { label: "Status" }
  for (const item of data) {
    row[item.status] = item.count
  }
  const chartData = [row]
  const total = data.reduce((sum, item) => sum + item.count, 0)

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
          color: ATTENDANCE_COLORS[item.status] ?? "var(--muted-foreground)",
        }))}
      />
      <p className="mt-2 text-right text-xs text-muted-foreground">{total} subject records</p>
    </ChartCard>
  )
}

function SubjectAttendanceTable({
  rows,
  total,
}: {
  rows: SubjectAttendanceRow[]
  total: number
}) {
  return (
    <ChartCard
      title="Subject Attendance"
      subtitle="Subject-level averages, shortage and eligibility in the selected scope"
      status={rows.length > 0 ? "ready" : "empty"}
      emptyIcon={BookOpen}
      emptyTitle="No subject data"
      emptyDescription="No subjects match the current filters."
      exportFileName="admin_subject_attendance.csv"
      exportColumns={[
        { key: "subject_code", label: "Subject Code" },
        { key: "subject_name", label: "Subject" },
        { key: "department_name", label: "Department" },
        { key: "semester", label: "Semester" },
        { key: "student_count", label: "Students" },
        { key: "avg_attendance", label: "Avg Attendance" },
        { key: "below_target_count", label: "Below Target" },
        { key: "critical_shortage_count", label: "Critical Shortage" },
        { key: "eligible_count", label: "Eligible" },
        { key: "not_eligible_count", label: "Not Eligible" },
      ]}
      exportRows={rows as unknown as Array<Record<string, unknown>>}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1100px] text-left text-sm">
          <colgroup>
            <col className="w-[220px]" />
            <col className="w-[200px]" />
            <col className="w-[60px]" />
            <col className="w-[80px]" />
            <col className="w-[80px]" />
            <col className="w-[100px]" />
            <col className="w-[80px]" />
            <col className="w-[80px]" />
            <col className="w-[100px]" />
          </colgroup>
          <thead>
            <tr className="border-b bg-muted/50 text-xs text-muted-foreground uppercase">
              <th className="py-2.5 pl-4 pr-3 font-medium">Subject</th>
              <th className="py-2.5 pl-4 pr-3 font-medium">Department</th>
              <th className="py-2.5 pl-4 pr-3 text-right font-medium">Sem</th>
              <th className="py-2.5 pl-4 pr-3 text-right font-medium">Students</th>
              <th className="py-2.5 pl-4 pr-3 text-right font-medium">Avg %</th>
              <th className="py-2.5 pl-4 pr-3 text-right font-medium">Below Target</th>
              <th className="py-2.5 pl-4 pr-3 text-right font-medium">Critical</th>
              <th className="py-2.5 pl-4 pr-3 text-right font-medium">Eligible</th>
              <th className="py-2.5 pl-4 pr-3 text-right font-medium">Not Eligible</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.subject_code}-${row.semester}`} className="border-b last:border-0">
                <td className="py-2.5 pl-4 pr-3">
                  <p className="font-medium leading-snug" title={`${row.subject_name} (${row.subject_code})`}>
                    {row.subject_name}
                  </p>
                  <p className="text-xs text-muted-foreground">{row.subject_code}</p>
                </td>
                <td className="py-2.5 pl-4 pr-3 text-xs leading-snug">{row.department_name}</td>
                <td className="py-2.5 pl-4 pr-3 text-right tabular-nums">{row.semester}</td>
                <td className="py-2.5 pl-4 pr-3 text-right tabular-nums">{row.student_count}</td>
                <td className="py-2.5 pl-4 pr-3 text-right tabular-nums">
                  {withSuffix(row.avg_attendance, "%")}
                </td>
                <td className="py-2.5 pl-4 pr-3 text-right tabular-nums text-chart-3">
                  {row.below_target_count}
                </td>
                <td className="py-2.5 pl-4 pr-3 text-right tabular-nums text-destructive">
                  {row.critical_shortage_count}
                </td>
                <td className="py-2.5 pl-4 pr-3 text-right tabular-nums text-chart-2">
                  {row.eligible_count}
                </td>
                <td className="py-2.5 pl-4 pr-3 text-right tabular-nums text-chart-5">
                  {row.not_eligible_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        {total} subject{total === 1 ? "" : "s"} in the selected scope
      </p>
    </ChartCard>
  )
}

export function AttendanceIntelligenceView({
  data,
  fetchedAt,
}: {
  data: AttendanceIntelligenceData
  fetchedAt: string
}) {
  const { kpis } = data

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Attendance Intelligence</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Institution attendance, shortage and eligibility from live records. Target from the
            Threshold Engine.
          </p>
        </div>
      </div>

      <AttendanceFilterBar filters={data.filters} />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-5">
        <StatCard
          label="Avg Attendance"
          value={withSuffix(kpis.avg_attendance, "%")}
          icon={CalendarCheck}
          hint={`Target ${toFixed(data.required_target)}%`}
        />
        <StatCard
          label="Below Target"
          value={String(kpis.students_below_target)}
          icon={AlertTriangle}
          tone="warning"
          hint="Students below target"
        />
        <StatCard
          label="Critical Shortage"
          value={String(kpis.critical_shortage_students)}
          icon={ShieldAlert}
          tone="destructive"
          hint="Needs immediate attention"
        />
        <StatCard
          label="Eligible"
          value={String(kpis.eligible_students)}
          icon={CheckCircle2}
          tone="success"
          hint="Above attendance target"
        />
        <StatCard
          label="Not Eligible"
          value={String(kpis.not_eligible_students)}
          icon={XCircle}
          tone="destructive"
          hint="Below attendance target"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <AttendanceByDepartmentCard data={data.by_department} />
        <AttendanceBySemesterCard data={data.by_semester} />
        <AttendanceDistributionCard data={data.distribution} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <SubjectAttendanceTable rows={data.subjects} total={data.subjects_total} />
        <ShortageStudentsGrouped
          rows={data.shortage_students}
          total={data.shortage_total}
          studentsTotal={data.shortage_students_total}
          requiredTarget={data.required_target}
        />
      </div>

      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span>
          Data refreshed {fetchedAt ? new Date(fetchedAt).toLocaleString() : "just now"}
        </span>
        <span className="flex items-center gap-1">
          <Users className="size-3.5" /> Showing top {data.limit} rows per table
        </span>
      </div>
    </div>
  )
}
