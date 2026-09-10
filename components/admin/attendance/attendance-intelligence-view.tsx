"use client"

import {
  AlertTriangle,
  BookOpen,
  CalendarCheck,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  TrendingUp,
  Users,
  XCircle,
} from "lucide-react"

import * as React from "react"

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

const SUBJECT_PAGE_SIZE = 10

function SubjectAttendanceTable({
  rows,
  total,
}: {
  rows: SubjectAttendanceRow[]
  total: number
}) {
  const [page, setPage] = React.useState(1)
  const totalPages = Math.max(1, Math.ceil(rows.length / SUBJECT_PAGE_SIZE))
  const safePage = Math.min(Math.max(1, page), totalPages)
  const start = (safePage - 1) * SUBJECT_PAGE_SIZE
  const pageRows = rows.slice(start, start + SUBJECT_PAGE_SIZE)

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
      <div className="overflow-hidden">
        <table className="w-full text-left text-xs" style={{ tableLayout: "fixed" }}>
          <colgroup>
            <col style={{ width: "22%" }} />
            <col style={{ width: "22%" }} />
            <col style={{ width: "6%" }} />
            <col style={{ width: "8%" }} />
            <col style={{ width: "9%" }} />
            <col style={{ width: "11%" }} />
            <col style={{ width: "8%" }} />
            <col style={{ width: "7%" }} />
            <col style={{ width: "7%" }} />
          </colgroup>
          <thead>
            <tr className="border-b bg-muted/50 text-[10px] text-muted-foreground uppercase">
              <th className="whitespace-normal px-2 py-2 font-medium leading-tight">Subject</th>
              <th className="whitespace-normal px-2 py-2 font-medium leading-tight">Department</th>
              <th className="whitespace-normal px-2 py-2 text-center font-medium leading-tight">Sem</th>
              <th className="whitespace-normal px-2 py-2 text-center font-medium leading-tight">Students</th>
              <th className="whitespace-normal px-2 py-2 text-center font-medium leading-tight">Avg %</th>
              <th className="whitespace-normal px-2 py-2 text-center font-medium leading-tight">Below Target</th>
              <th className="whitespace-normal px-2 py-2 text-center font-medium leading-tight">Critical</th>
              <th className="whitespace-normal px-2 py-2 text-center font-medium leading-tight">Eligible</th>
              <th className="whitespace-normal px-2 py-2 text-center font-medium leading-tight">Not Eligible</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row) => (
              <tr key={`${row.subject_code}-${row.semester}`} className="border-b last:border-0">
                <td className="px-2 py-2">
                  <p className="font-medium leading-snug break-words" title={`${row.subject_name} (${row.subject_code})`}>
                    {row.subject_name}
                  </p>
                  <p className="text-[10px] text-muted-foreground">{row.subject_code}</p>
                </td>
                <td className="px-2 py-2 leading-snug break-words">{row.department_name}</td>
                <td className="px-2 py-2 text-center tabular-nums">{row.semester}</td>
                <td className="px-2 py-2 text-center tabular-nums">{row.student_count}</td>
                <td className="px-2 py-2 text-center tabular-nums">
                  {withSuffix(row.avg_attendance, "%")}
                </td>
                <td className="px-2 py-2 text-center tabular-nums text-chart-3">
                  {row.below_target_count}
                </td>
                <td className="px-2 py-2 text-center tabular-nums text-destructive">
                  {row.critical_shortage_count}
                </td>
                <td className="px-2 py-2 text-center tabular-nums text-chart-2">
                  {row.eligible_count}
                </td>
                <td className="px-2 py-2 text-center tabular-nums text-chart-5">
                  {row.not_eligible_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t pt-3">
          <p className="text-xs text-muted-foreground" aria-live="polite">
            Page {safePage} of {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={safePage <= 1}
              aria-label="Previous page"
              className="flex h-8 items-center gap-1 rounded-md border border-input bg-background px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50"
            >
              <ChevronLeft className="size-3.5" />
              Prev
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage >= totalPages}
              aria-label="Next page"
              className="flex h-8 items-center gap-1 rounded-md border border-input bg-background px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50 flex-row-reverse"
            >
              <ChevronRight className="size-3.5" />
              Next
            </button>
          </div>
        </div>
      )}
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

      <div className="flex flex-col gap-6">
        <SubjectAttendanceTable key={data.subjects_total} rows={data.subjects} total={data.subjects_total} />
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
