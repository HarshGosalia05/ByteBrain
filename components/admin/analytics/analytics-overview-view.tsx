"use client"

import Link from "next/link"
import {
  AlertTriangle,
  BookOpen,
  Building2,
  CalendarCheck,
  GraduationCap,
  Users,
} from "lucide-react"

import type {
  DepartmentOverview,
  SemesterPerformanceDistribution,
  AttendanceDistribution,
  BacklogDistribution,
  AtRiskStudentsResult,
  SubjectsNeedingAttentionResult,
} from "@/lib/analytics-api"

import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
import { DonutChart } from "@/components/shared/charts/donut-chart"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"
import { EmptyState } from "@/components/shared/state/empty-state"

function fixed(v: number | null | undefined, d = 2): string {
  if (v == null) return "—"
  return v.toFixed(d)
}

const PERF_COLORS: Record<string, string> = {
  Top: "var(--chart-2)",
  "Above Average": "var(--chart-1)",
  Average: "var(--chart-3)",
  "Below Average": "var(--chart-4)",
  "Low Performer": "var(--chart-5)",
}

const ATT_COLORS: Record<string, string> = {
  Excellent: "var(--chart-2)",
  Good: "var(--chart-1)",
  Average: "var(--chart-3)",
  Low: "var(--chart-4)",
  Critical: "var(--chart-5)",
}

type Props = {
  department: DepartmentOverview | null
  performance: SemesterPerformanceDistribution | null
  attendance: AttendanceDistribution | null
  backlog: BacklogDistribution | null
  risk: AtRiskStudentsResult | null
  subjects: SubjectsNeedingAttentionResult | null
}

export function AnalyticsOverviewView({
  department,
  performance,
  attendance,
  backlog,
  risk,
  subjects,
}: Props) {
  const deptName = department?.department_name ?? "All Departments"
  const semLabel = department?.semester_no ? `Sem ${department.semester_no}` : "All Semesters"

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">Analytics Overview</h1>
        <p className="text-sm text-muted-foreground">
          {deptName} &middot; {semLabel}
          {department?.academic_year ? ` &middot; ${department.academic_year}` : ""}
        </p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total Students" value={String(department?.total_students ?? 0)} icon={Users} tone="primary" />
        <StatCard label="Avg SGPA" value={fixed(department?.average_sgpa)} icon={GraduationCap} tone="primary" />
        <StatCard label="Avg Attendance" value={department?.average_attendance_percentage != null ? `${fixed(department.average_attendance_percentage)}%` : "—"} icon={CalendarCheck} tone={department && department.average_attendance_percentage != null && department.average_attendance_percentage < 75 ? "warning" : "success"} />
        <StatCard label="At-Risk Students" value={String(risk?.total_flagged ?? 0)} icon={AlertTriangle} tone={risk && risk.total_flagged > 0 ? "destructive" : "success"} />
      </div>

      {/* Charts Row */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Performance Distribution"
          subtitle="Students by performance band"
          status={performance && performance.buckets.length > 0 ? "ready" : "empty"}
          emptyTitle="No performance data"
        >
          {performance && (
            <SubjectBarChart
              data={performance.buckets.map((b) => ({ label: b.label, count: b.count }))}
              xKey="label"
              dataKey="count"
              color="var(--chart-1)"
              height={220}
            />
          )}
        </ChartCard>

        <ChartCard
          title="Attendance Distribution"
          subtitle="Students by attendance band"
          status={attendance && attendance.buckets.length > 0 ? "ready" : "empty"}
          emptyTitle="No attendance data"
        >
          {attendance && (
            <DonutChart
              data={attendance.buckets.map((b) => ({
                name: b.band,
                value: b.count,
                color: ATT_COLORS[b.band] ?? "var(--muted-foreground)",
              }))}
              height={210}
              centerValue={String(attendance.total_students)}
              centerLabel="Students"
            />
          )}
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Backlog Distribution"
          subtitle="Students by backlog count range"
          status={backlog && backlog.buckets.length > 0 ? "ready" : "empty"}
          emptyTitle="No backlog data"
        >
          {backlog && (
            <SubjectBarChart
              data={backlog.buckets.map((b) => ({ range: b.backlog_range, count: b.count }))}
              xKey="range"
              dataKey="count"
              color="var(--chart-4)"
              height={220}
            />
          )}
        </ChartCard>

        <ChartCard
          title="Subjects Needing Attention"
          subtitle={`${subjects?.total_flagged ?? 0} subjects flagged`}
          status={subjects && subjects.subjects.length > 0 ? "ready" : "empty"}
          emptyTitle="No subjects flagged"
          emptyDescription="All subjects are performing within thresholds."
        >
          {subjects && subjects.subjects.length > 0 && (
            <div className="max-h-64 overflow-y-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="pb-2 pr-4 font-medium">Subject</th>
                    <th className="pb-2 pr-4 font-medium">Avg %</th>
                    <th className="pb-2 pr-4 font-medium">Fail Rate</th>
                    <th className="pb-2 font-medium">Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {subjects.subjects.map((s) => (
                    <tr key={s.subject_id} className="border-b last:border-0">
                      <td className="py-2 pr-4">
                        <Link href={`/admin/analytics/subjects/${s.subject_id}`} className="text-primary underline-offset-2 hover:underline">
                          {s.subject_code ?? s.subject_id}
                        </Link>
                      </td>
                      <td className="py-2 pr-4 tabular-nums">{fixed(s.average_percentage)}%</td>
                      <td className="py-2 pr-4 tabular-nums">{fixed(s.fail_rate)}%</td>
                      <td className="py-2 text-xs text-muted-foreground">{s.reasons[0] ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </ChartCard>
      </div>
    </div>
  )
}
