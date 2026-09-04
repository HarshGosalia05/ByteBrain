"use client"

import { GraduationCap, Users } from "lucide-react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"

import type { AdminStudentRow, AdminStudentsData } from "@/lib/admin-api"

import { ChartCard } from "@/components/shared/data/chart-card"
import { StudentsFilterBar } from "@/components/admin/students/students-filter-bar"
import { StudentsPagination } from "@/components/admin/students/students-pagination"

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

function RiskBadge({ level }: { level: string | null }) {
  if (!level) {
    return <span className="text-xs text-muted-foreground">—</span>
  }
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

function StudentsTable({
  rows,
  total,
  limit,
  offset,
}: {
  rows: AdminStudentRow[]
  total: number
  limit: number
  offset: number
}) {
  const searchParams = useSearchParams()
  const queryString = searchParams?.toString() ? `?${searchParams.toString()}` : ""

  return (
    <ChartCard
      title="Students"
      subtitle="Institution-wide read-only student overview"
      status={rows.length > 0 ? "ready" : "empty"}
      emptyIcon={Users}
      emptyTitle="No students found"
      emptyDescription="No students match the current filters or search."
      exportFileName="admin_students.csv"
      exportColumns={[
        { key: "student_id", label: "Student ID" },
        { key: "student_name", label: "Student" },
        { key: "enrollment_no", label: "Enrollment" },
        { key: "department_name", label: "Department" },
        { key: "semester", label: "Semester" },
        { key: "academic_year", label: "Academic Year" },
        { key: "sgpa", label: "SGPA" },
        { key: "cgpa", label: "CGPA" },
        { key: "percentage", label: "Percentage" },
        { key: "attendance", label: "Attendance" },
        { key: "backlogs", label: "Backlogs" },
        { key: "risk", label: "Risk" },
        { key: "academic_standing", label: "Academic Standing" },
      ]}
      exportRows={rows as unknown as Array<Record<string, unknown>>}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-200 text-left text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground uppercase">
              <th className="py-2 pr-4 font-medium">Student</th>
              <th className="py-2 pr-4 text-right font-medium">Enrollment</th>
              <th className="py-2 pr-4 font-medium">Department</th>
              <th className="py-2 pr-4 text-right font-medium">Sem</th>
              <th className="py-2 pr-4 text-right font-medium">SGPA</th>
              <th className="py-2 pr-4 text-right font-medium">CGPA</th>
              <th className="py-2 pr-4 text-right font-medium">Percentage</th>
              <th className="py-2 pr-4 text-right font-medium">Attendance</th>
              <th className="py-2 pr-4 text-right font-medium">Backlogs</th>
              <th className="py-2 pr-4 font-medium">Risk</th>
              <th className="py-2 text-right font-medium">Standing</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const profileHref = `/admin/students/${encodeURIComponent(row.student_id)}${queryString}`
              return (
                <tr
                  key={row.student_id}
                  className="border-b last:border-0 cursor-pointer transition-colors hover:bg-muted/40"
                >
                  <td className="py-2.5 pr-4">
                    <Link href={profileHref} className="block">
                      <p className="max-w-52 truncate font-medium" title={row.student_name}>
                        {row.student_name}
                      </p>
                      <p className="text-xs text-muted-foreground">{row.student_id}</p>
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    <Link href={profileHref} className="block">
                      {row.enrollment_no}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4 text-xs">
                    <Link href={profileHref} className="block">
                      {row.department_name || "—"}
                      <p className="text-xs text-muted-foreground">{row.academic_year ?? ""}</p>
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    <Link href={profileHref} className="block">
                      {row.semester ?? "—"}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    <Link href={profileHref} className="block">
                      {toFixed(row.sgpa)}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    <Link href={profileHref} className="block">
                      {toFixed(row.cgpa)}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    <Link href={profileHref} className="block">
                      {withSuffix(row.percentage, "%")}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    <Link href={profileHref} className="block">
                      {withSuffix(row.attendance, "%")}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    <Link href={profileHref} className="block">
                      {row.backlogs ?? "—"}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4">
                    <Link href={profileHref} className="block">
                      <RiskBadge level={row.risk} />
                    </Link>
                  </td>
                  <td className="py-2.5 text-right text-xs">
                    <Link href={profileHref} className="block">
                      {row.academic_standing ?? "—"}
                    </Link>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <StudentsPagination total={total} limit={limit} offset={offset} />
    </ChartCard>
  )
}

export function StudentsView({
  data,
  fetchedAt,
}: {
  data: AdminStudentsData
  fetchedAt: string
}) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Students</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Read-only institution overview of every student and their stored
            academic snapshot.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-md bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
          <GraduationCap className="size-3.5" />
          {data.students_total} total
        </span>
      </div>

      <StudentsFilterBar filters={data.filters} />

      <StudentsTable
        rows={data.students}
        total={data.students_total}
        limit={data.limit}
        offset={data.offset}
      />

      <p className="text-xs text-muted-foreground">
        Data refreshed {fetchedAt ? new Date(fetchedAt).toLocaleString() : "just now"}
      </p>
    </div>
  )
}
