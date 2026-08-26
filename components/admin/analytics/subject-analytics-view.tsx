"use client"

import Link from "next/link"
import { ArrowLeft, BookOpen, CalendarCheck, GraduationCap, Users } from "lucide-react"

import type {
  SubjectPerformanceSummary,
  SubjectAttendanceSummary,
  SubjectUnderperformers,
} from "@/lib/analytics-api"

import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
import { DonutChart } from "@/components/shared/charts/donut-chart"
import { EmptyState } from "@/components/shared/state/empty-state"

function fixed(v: number | null | undefined, d = 2): string {
  if (v == null) return "—"
  return v.toFixed(d)
}

const GRADE_COLORS: Record<string, string> = {
  "O": "var(--chart-2)",
  "A+": "var(--chart-2)",
  "A": "var(--chart-1)",
  "B+": "var(--chart-1)",
  "B": "var(--chart-3)",
  "C": "var(--chart-3)",
  "F": "var(--chart-5)",
  "RA": "var(--chart-5)",
  "SA": "var(--chart-4)",
}

type Props = {
  performance: SubjectPerformanceSummary | null
  attendance: SubjectAttendanceSummary | null
  underperformers: SubjectUnderperformers | null
}

export function SubjectAnalyticsView({ performance, attendance, underperformers }: Props) {
  const title = performance?.subject_name ?? performance?.subject_code ?? performance?.subject_id ?? "Subject"
  const gradeData = performance?.grade_distribution.map((g) => ({
    name: g.grade,
    value: g.count,
    color: GRADE_COLORS[g.grade] ?? "var(--muted-foreground)",
  })) ?? []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/admin/analytics" className="mb-1 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to Analytics
        </Link>
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="text-sm text-muted-foreground">
          {performance?.subject_id}
          {performance?.semester_no ? ` · Sem ${performance.semester_no}` : ""}
        </p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Students" value={String(performance?.total_students ?? 0)} icon={Users} tone="primary" />
        <StatCard label="Avg %" value={performance?.average_percentage != null ? `${fixed(performance.average_percentage)}%` : "—"} icon={GraduationCap} tone="primary" />
        <StatCard label="Pass Rate" value={performance?.pass_rate != null ? `${fixed(performance.pass_rate)}%` : "—"} icon={BookOpen} tone={performance && performance.pass_rate != null && performance.pass_rate < 80 ? "warning" : "success"} />
        <StatCard label="Avg Attendance" value={attendance?.average_attendance_percentage != null ? `${fixed(attendance.average_attendance_percentage)}%` : "—"} icon={CalendarCheck} tone={attendance && attendance.average_attendance_percentage != null && attendance.average_attendance_percentage < 75 ? "warning" : "success"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Grade distribution */}
        <ChartCard
          title="Grade Distribution"
          subtitle={`${performance?.grade_distribution.length ?? 0} grades`}
          status={gradeData.length > 0 ? "ready" : "empty"}
          emptyTitle="No grade data"
        >
          {gradeData.length > 0 && (
            <DonutChart
              data={gradeData}
              height={210}
              centerValue={String(performance?.total_students ?? 0)}
              centerLabel="Students"
            />
          )}
        </ChartCard>

        {/* Performance stats */}
        <ChartCard
          title="Performance Summary"
          status="ready"
        >
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Median %</p>
              <p className="text-lg font-semibold">{fixed(performance?.median_percentage)}%</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Min %</p>
              <p className="text-lg font-semibold">{fixed(performance?.min_percentage)}%</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Max %</p>
              <p className="text-lg font-semibold">{fixed(performance?.max_percentage)}%</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Pass / Fail</p>
              <p className="text-lg font-semibold">
                {performance?.pass_count ?? 0} / {performance?.fail_count ?? 0}
              </p>
            </div>
          </div>
        </ChartCard>
      </div>

      {/* Attendance details */}
      {attendance && (
        <ChartCard
          title="Attendance Summary"
          subtitle={`${attendance.total_students} students enrolled`}
          status="ready"
        >
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Eligible</p>
              <p className="text-lg font-semibold text-green-600 dark:text-green-400">{attendance.eligible_count}</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">At Risk</p>
              <p className="text-lg font-semibold text-yellow-600 dark:text-yellow-400">{attendance.at_risk_count}</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Ineligible</p>
              <p className="text-lg font-semibold text-red-600 dark:text-red-400">{attendance.ineligible_count}</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Shortage Flag</p>
              <p className="text-lg font-semibold">{attendance.shortage_count}</p>
            </div>
          </div>
        </ChartCard>
      )}

      {/* Underperformers */}
      {underperformers && underperformers.students.length > 0 && (
        <ChartCard
          title="Underperformers"
          subtitle={`Threshold: ${underperformers.threshold}%`}
          status="ready"
        >
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Student</th>
                  <th className="pb-2 pr-4 font-medium">%</th>
                  <th className="pb-2 pr-4 font-medium">Grade</th>
                  <th className="pb-2 font-medium">Attendance</th>
                </tr>
              </thead>
              <tbody>
                {underperformers.students.map((s) => (
                  <tr key={s.student_id} className="border-b last:border-0">
                    <td className="py-2 pr-4">
                      <Link href={`/admin/analytics/students/${s.student_id}`} className="text-primary underline-offset-2 hover:underline">
                        {s.full_name ?? s.student_id}
                      </Link>
                    </td>
                    <td className="py-2 pr-4 tabular-nums">{fixed(s.percentage)}%</td>
                    <td className="py-2 pr-4">{s.grade ?? "—"}</td>
                    <td className="py-2 tabular-nums">{fixed(s.attendance_percentage)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      )}
    </div>
  )
}
