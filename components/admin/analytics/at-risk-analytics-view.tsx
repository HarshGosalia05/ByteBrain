"use client"

import Link from "next/link"
import { AlertTriangle, ArrowLeft, BookOpen, Users } from "lucide-react"

import type {
  AtRiskStudentsResult,
  BelowThresholdResult,
  SubjectsNeedingAttentionResult,
} from "@/lib/analytics-api"

import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
import { EmptyState } from "@/components/shared/state/empty-state"

function fixed(v: number | null | undefined, d = 2): string {
  if (v == null) return "—"
  return v.toFixed(d)
}

type Props = {
  risk: AtRiskStudentsResult | null
  threshold: BelowThresholdResult | null
  subjects: SubjectsNeedingAttentionResult | null
}

export function AtRiskAnalyticsView({ risk, threshold, subjects }: Props) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/admin/analytics" className="mb-1 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to Analytics
        </Link>
        <h1 className="text-xl font-semibold">At-Risk Analytics</h1>
        <p className="text-sm text-muted-foreground">
          Students and subjects flagged by automated risk detection.
        </p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="At-Risk Students" value={String(risk?.total_flagged ?? 0)} icon={AlertTriangle} tone={risk && risk.total_flagged > 0 ? "destructive" : "success"} />
        <StatCard label="Below Threshold" value={String(threshold?.total_flagged ?? 0)} icon={AlertTriangle} tone={threshold && threshold.total_flagged > 0 ? "warning" : "success"} />
        <StatCard label="Subjects Flagged" value={String(subjects?.total_flagged ?? 0)} icon={BookOpen} tone={subjects && subjects.total_flagged > 0 ? "warning" : "success"} />
        <StatCard label="Threshold" value={threshold?.threshold != null ? `${threshold.threshold}%` : "—"} icon={Users} tone="primary" />
      </div>

      {/* At-Risk Students */}
      <ChartCard
        title="At-Risk Students"
        subtitle={`${risk?.total_flagged ?? 0} students flagged`}
        status={risk && risk.students.length > 0 ? "ready" : "empty"}
        emptyTitle="No at-risk students"
        emptyDescription="No students currently meet the at-risk criteria."
      >
        {risk && risk.students.length > 0 && (
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Student</th>
                  <th className="pb-2 pr-4 font-medium">CGPA</th>
                  <th className="pb-2 pr-4 font-medium">Backlogs</th>
                  <th className="pb-2 pr-4 font-medium">Attendance</th>
                  <th className="pb-2 font-medium">Reasons</th>
                </tr>
              </thead>
              <tbody>
                {risk.students.map((s) => (
                  <tr key={s.student_id} className="border-b last:border-0">
                    <td className="py-2 pr-4">
                      <Link href={`/admin/analytics/students/${s.student_id}`} className="text-primary underline-offset-2 hover:underline">
                        {s.full_name ?? s.student_id}
                      </Link>
                    </td>
                    <td className="py-2 pr-4 tabular-nums">{fixed(s.overall_cgpa)}</td>
                    <td className="py-2 pr-4 tabular-nums">
                      <span className={s.total_backlogs > 0 ? "text-red-600 dark:text-red-400" : ""}>
                        {s.total_backlogs}
                      </span>
                    </td>
                    <td className="py-2 pr-4 tabular-nums">
                      <span className={(s.overall_attendance_percentage ?? 100) < 75 ? "text-yellow-600 dark:text-yellow-400" : ""}>
                        {fixed(s.overall_attendance_percentage)}%
                      </span>
                    </td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-1">
                        {s.risk_reasons.map((r, i) => (
                          <span key={i} className="inline-flex rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                            {r}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ChartCard>

      {/* Below Threshold */}
      <ChartCard
        title="Below Attendance Threshold"
        subtitle={`${threshold?.total_flagged ?? 0} students below ${threshold?.threshold ?? "—"}%`}
        status={threshold && threshold.students.length > 0 ? "ready" : "empty"}
        emptyTitle="No students below threshold"
        emptyDescription="All students are above the attendance eligibility threshold."
      >
        {threshold && threshold.students.length > 0 && (
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Student</th>
                  <th className="pb-2 pr-4 font-medium">Subject</th>
                  <th className="pb-2 pr-4 font-medium">Attended</th>
                  <th className="pb-2 pr-4 font-medium">Total</th>
                  <th className="pb-2 pr-4 font-medium">%</th>
                  <th className="pb-2 font-medium">Classes Needed</th>
                </tr>
              </thead>
              <tbody>
                {threshold.students.map((s) => (
                  <tr key={`${s.student_id}-${s.subject_id}`} className="border-b last:border-0">
                    <td className="py-2 pr-4">
                      <Link href={`/admin/analytics/students/${s.student_id}`} className="text-primary underline-offset-2 hover:underline">
                        {s.full_name ?? s.student_id}
                      </Link>
                    </td>
                    <td className="py-2 pr-4">{s.subject_code ?? s.subject_id}</td>
                    <td className="py-2 pr-4 tabular-nums">{s.attended_classes}</td>
                    <td className="py-2 pr-4 tabular-nums">{s.total_classes}</td>
                    <td className="py-2 pr-4 tabular-nums text-yellow-600 dark:text-yellow-400">
                      {fixed(s.attendance_percentage)}%
                    </td>
                    <td className="py-2 tabular-nums">{s.classes_needed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ChartCard>

      {/* Subjects Needing Attention */}
      <ChartCard
        title="Subjects Needing Attention"
        subtitle={`${subjects?.total_flagged ?? 0} subjects flagged`}
        status={subjects && subjects.subjects.length > 0 ? "ready" : "empty"}
        emptyTitle="No subjects flagged"
        emptyDescription="All subjects are performing within thresholds."
      >
        {subjects && subjects.subjects.length > 0 && (
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Subject</th>
                  <th className="pb-2 pr-4 font-medium">Students</th>
                  <th className="pb-2 pr-4 font-medium">Avg %</th>
                  <th className="pb-2 pr-4 font-medium">Fail Rate</th>
                  <th className="pb-2 pr-4 font-medium">Avg Attendance</th>
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
                    <td className="py-2 pr-4 tabular-nums">{s.total_students}</td>
                    <td className="py-2 pr-4 tabular-nums">{fixed(s.average_percentage)}%</td>
                    <td className="py-2 pr-4 tabular-nums">{fixed(s.fail_rate)}%</td>
                    <td className="py-2 pr-4 tabular-nums">{fixed(s.average_attendance)}%</td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-1">
                        {s.reasons.map((r, i) => (
                          <span key={i} className="inline-flex rounded-full bg-yellow-50 px-2 py-0.5 text-xs font-medium text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">
                            {r}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ChartCard>
    </div>
  )
}
