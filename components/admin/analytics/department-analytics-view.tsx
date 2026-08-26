"use client"

import Link from "next/link"
import { ArrowLeft, Building2, GraduationCap, Users, AlertTriangle } from "lucide-react"

import type {
  DepartmentOverview,
  SemesterPerformanceDistribution,
  AttendanceDistribution,
  BacklogDistribution,
} from "@/lib/analytics-api"

import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
import { DonutChart } from "@/components/shared/charts/donut-chart"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"

function fixed(v: number | null | undefined, d = 2): string {
  if (v == null) return "—"
  return v.toFixed(d)
}

const ATT_COLORS: Record<string, string> = {
  Excellent: "var(--chart-2)",
  Good: "var(--chart-1)",
  Average: "var(--chart-3)",
  Low: "var(--chart-4)",
  Critical: "var(--chart-5)",
}

type Props = {
  overview: DepartmentOverview | null
  performance: SemesterPerformanceDistribution | null
  attendance: AttendanceDistribution | null
  backlog: BacklogDistribution | null
}

export function DepartmentAnalyticsView({ overview, performance, attendance, backlog }: Props) {
  const deptName = overview?.department_name ?? "All Departments"
  const semLabel = overview?.semester_no ? `Sem ${overview.semester_no}` : "All Semesters"

  const perfData = performance?.buckets.map((b) => ({
    label: b.label,
    count: b.count,
  })) ?? []

  const attData = attendance?.buckets.map((b) => ({
    name: b.band,
    value: b.count,
    color: ATT_COLORS[b.band] ?? "var(--muted-foreground)",
  })) ?? []

  const backlogData = backlog?.buckets.map((b) => ({
    range: b.backlog_range,
    count: b.count,
  })) ?? []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/admin/analytics" className="mb-1 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to Analytics
        </Link>
        <h1 className="text-xl font-semibold">Department Analytics</h1>
        <p className="text-sm text-muted-foreground">
          {deptName} · {semLabel}
          {overview?.academic_year ? ` · ${overview.academic_year}` : ""}
        </p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Students" value={String(overview?.total_students ?? 0)} icon={Users} tone="primary" />
        <StatCard label="Avg SGPA" value={fixed(overview?.average_sgpa)} icon={GraduationCap} tone="primary" />
        <StatCard label="Avg Attendance" value={overview?.average_attendance_percentage != null ? `${fixed(overview.average_attendance_percentage)}%` : "—"} icon={Building2} tone={overview && overview.average_attendance_percentage != null && overview.average_attendance_percentage < 75 ? "warning" : "success"} />
        <StatCard label="With Backlogs" value={String(overview?.students_with_backlogs ?? 0)} icon={AlertTriangle} tone={overview && overview.students_with_backlogs > 0 ? "warning" : "success"} />
      </div>

      {/* Charts Row 1 */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Performance Distribution"
          subtitle={`${performance?.total_students ?? 0} students`}
          status={perfData.length > 0 ? "ready" : "empty"}
          emptyTitle="No performance data"
        >
          {perfData.length > 0 && (
            <SubjectBarChart
              data={perfData}
              xKey="label"
              dataKey="count"
              color="var(--chart-1)"
              height={220}
            />
          )}
        </ChartCard>

        <ChartCard
          title="Attendance Distribution"
          subtitle={`${attendance?.total_students ?? 0} students`}
          status={attData.length > 0 ? "ready" : "empty"}
          emptyTitle="No attendance data"
        >
          {attData.length > 0 && (
            <DonutChart
              data={attData}
              height={210}
              centerValue={String(attendance?.total_students ?? 0)}
              centerLabel="Students"
            />
          )}
        </ChartCard>
      </div>

      {/* Backlog distribution */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Backlog Distribution"
          subtitle={`${backlog?.students_with_backlogs ?? 0} of ${backlog?.total_students ?? 0} students have backlogs`}
          status={backlogData.length > 0 ? "ready" : "empty"}
          emptyTitle="No backlog data"
        >
          {backlogData.length > 0 && (
            <SubjectBarChart
              data={backlogData}
              xKey="range"
              dataKey="count"
              color="var(--chart-4)"
              height={220}
            />
          )}
        </ChartCard>

        <ChartCard
          title="Performance Stats"
          status="ready"
        >
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Total Students</p>
              <p className="text-lg font-semibold">{overview?.total_students ?? 0}</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Avg SGPA</p>
              <p className="text-lg font-semibold">{fixed(overview?.average_sgpa)}</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Avg %</p>
              <p className="text-lg font-semibold">{fixed(overview?.average_percentage)}%</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Total Backlogs</p>
              <p className="text-lg font-semibold">{overview?.total_backlogs ?? 0}</p>
            </div>
          </div>
        </ChartCard>
      </div>
    </div>
  )
}
