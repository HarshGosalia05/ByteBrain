"use client"

import Link from "next/link"
import { ArrowLeft, AlertTriangle, CalendarCheck, BookOpen, GraduationCap } from "lucide-react"

import type {
  StudentAcademicProfile,
  StudentSemesterHistory,
  StudentAttendanceSummary,
  StudentBacklogSummary,
} from "@/lib/analytics-api"

import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
import { TrendChart } from "@/components/shared/charts/trend-chart"
import { DonutChart } from "@/components/shared/charts/donut-chart"
import { EmptyState } from "@/components/shared/state/empty-state"

function fixed(v: number | null | undefined, d = 2): string {
  if (v == null) return "—"
  return v.toFixed(d)
}

function semLabel(s: number): string {
  return `Sem ${s}`
}

type Props = {
  profile: StudentAcademicProfile | null
  history: StudentSemesterHistory | null
  attendance: StudentAttendanceSummary | null
  backlog: StudentBacklogSummary | null
}

export function StudentAnalyticsView({ profile, history, attendance, backlog }: Props) {
  const title = profile?.full_name ?? profile?.student_id ?? "Student"
  const sgpaTrend = history?.semesters.map((s) => ({
    label: semLabel(s.semester_no),
    sgpa: s.semester_sgpa ?? 0,
    percentage: s.semester_percentage ?? 0,
  })) ?? []

  const attStatusData = [
    { name: "Present", value: attendance?.attended_classes ?? 0, color: "var(--chart-2)" },
    { name: "Absent", value: (attendance?.total_classes ?? 0) - (attendance?.attended_classes ?? 0), color: "var(--chart-4)" },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/admin/analytics" className="mb-1 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to Analytics
        </Link>
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="text-sm text-muted-foreground">
          {profile?.student_id}
          {profile?.department_name ? ` · ${profile.department_name}` : ""}
          {profile?.current_semester ? ` · Sem ${profile.current_semester}` : ""}
        </p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Latest SGPA" value={fixed(profile?.latest_sgpa)} icon={BookOpen} tone="primary" />
        <StatCard label="CGPA" value={fixed(profile?.overall_cgpa)} icon={GraduationCap} tone="primary" />
        <StatCard label="Attendance" value={profile?.overall_attendance_percentage != null ? `${fixed(profile.overall_attendance_percentage)}%` : "—"} icon={CalendarCheck} tone={profile && profile.overall_attendance_percentage != null && profile.overall_attendance_percentage < 75 ? "warning" : "success"} />
        <StatCard label="Backlogs" value={String(profile?.total_backlogs ?? 0)} icon={AlertTriangle} tone={profile && profile.total_backlogs > 0 ? "destructive" : "success"} />
      </div>

      {/* SGPA Trend */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="SGPA Trend"
          subtitle="Semester-wise SGPA progression"
          status={sgpaTrend.length > 0 ? "ready" : "empty"}
          emptyTitle="No semester history"
        >
          {sgpaTrend.length > 0 && (
            <TrendChart
              data={sgpaTrend.map((d) => ({ label: d.label, sgpa: d.sgpa }))}
              xKey="label"
              series={[{ key: "sgpa", label: "SGPA", color: "var(--chart-1)" }]}
              height={220}
            />
          )}
        </ChartCard>

        <ChartCard
          title="Attendance Overview"
          subtitle={`Sem ${attendance?.semester_no ?? profile?.current_semester ?? "—"}`}
          status={attendance && attendance.total_classes > 0 ? "ready" : "empty"}
          emptyTitle="No attendance data"
        >
          {attendance && (
            <div className="flex flex-col items-center gap-4">
              <DonutChart
                data={attStatusData}
                height={160}
                centerValue={attendance.overall_attendance_percentage != null ? `${fixed(attendance.overall_attendance_percentage)}%` : "—"}
                centerLabel="Attendance"
              />
              <div className="grid w-full grid-cols-2 gap-4">
                <div className="text-center">
                  <p className="text-2xl font-semibold">{attendance.total_classes}</p>
                  <p className="text-xs text-muted-foreground">Total Classes</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-semibold">{attendance.attended_classes}</p>
                  <p className="text-xs text-muted-foreground">Attended</p>
                </div>
              </div>
            </div>
          )}
        </ChartCard>
      </div>

      {/* Subject-level attendance */}
      {attendance && attendance.subjects.length > 0 && (
        <ChartCard
          title="Subject-wise Attendance"
          subtitle={`${attendance.subjects.length} subjects`}
          status="ready"
        >
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Subject</th>
                  <th className="pb-2 pr-4 font-medium">Attended</th>
                  <th className="pb-2 pr-4 font-medium">Total</th>
                  <th className="pb-2 pr-4 font-medium">%</th>
                  <th className="pb-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {attendance.subjects.map((s) => (
                  <tr key={s.subject_id} className="border-b last:border-0">
                    <td className="py-2 pr-4">{s.subject_code ?? s.subject_id}</td>
                    <td className="py-2 pr-4 tabular-nums">{s.attended_classes}</td>
                    <td className="py-2 pr-4 tabular-nums">{s.total_classes}</td>
                    <td className="py-2 pr-4 tabular-nums">{fixed(s.attendance_percentage)}%</td>
                    <td className="py-2">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        (s.attendance_percentage ?? 0) >= 75
                          ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                          : (s.attendance_percentage ?? 0) >= 60
                            ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
                            : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
                      }`}>
                        {s.attendance_status ?? "—"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      )}

      {/* Backlogs */}
      {backlog && backlog.backlogs.length > 0 && (
        <ChartCard
          title="Backlog Details"
          subtitle={`${backlog.total_backlogs} active backlogs`}
          status="ready"
        >
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Subject</th>
                  <th className="pb-2 pr-4 font-medium">Sem</th>
                  <th className="pb-2 pr-4 font-medium">%</th>
                  <th className="pb-2 font-medium">Grade</th>
                </tr>
              </thead>
              <tbody>
                {backlog.backlogs.map((b) => (
                  <tr key={b.subject_id} className="border-b last:border-0">
                    <td className="py-2 pr-4">{b.subject_code ?? b.subject_id}</td>
                    <td className="py-2 pr-4 tabular-nums">{b.semester_no ?? "—"}</td>
                    <td className="py-2 pr-4 tabular-nums">{fixed(b.percentage)}%</td>
                    <td className="py-2">{b.grade ?? "—"}</td>
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
