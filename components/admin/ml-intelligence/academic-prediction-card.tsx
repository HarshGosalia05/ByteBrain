"use client"

import { BookOpen, GraduationCap, TrendingUp, Info, CircleAlert } from "lucide-react"
import type { AcademicPredictionIntelligence } from "@/lib/admin-api"
import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"

export function AcademicPredictionCard({ data }: { data: AcademicPredictionIntelligence }) {
  const { m1, m2 } = data

  const m1AvgMarkStr =
    m1.predicted_avg_subject_mark !== null && m1.predicted_avg_subject_mark !== undefined
      ? `${m1.predicted_avg_subject_mark.toFixed(1)} / 70`
      : "—"

  const m2AvgSgpaStr =
    m2.predicted_avg_next_sgpa !== null && m2.predicted_avg_next_sgpa !== undefined
      ? m2.predicted_avg_next_sgpa.toFixed(2)
      : "—"

  const m2AvgPctStr =
    m2.predicted_avg_next_percentage !== null && m2.predicted_avg_next_percentage !== undefined
      ? `${m2.predicted_avg_next_percentage.toFixed(1)}%`
      : "—"

  const hasM2Data = m2.department_performance_distribution.length > 0
  const sgpaTotal = m2.sgpa_distribution.reduce((sum, d) => sum + d.count, 0)
  const pctTotal = m2.percentage_distribution.reduce((sum, d) => sum + d.count, 0)

  return (
    <div className="flex flex-col gap-6">
      {/* M1 V2 availability notice — documented limitation, never fabricated */}
      <div className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-3">
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-medium">M1 V2 cohort analytics (not yet available)</p>
          <p className="text-xs text-muted-foreground">
            Institutional M1 V2 (Subject Marks Prediction) aggregate statistics are unavailable
            because the backend exposes M1 V2 per-student only, with no cohort endpoint and no
            persistence wiring. The validated M1 V2 predictions are surfaced per student for the
            Student and Faculty/Mentor experiences. No aggregate figures are shown here to avoid
            presenting unverified statistics.
          </p>
        </div>
      </div>

      {/* M2 V2 availability notice — documented limitation, never fabricated */}
      <div className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-3">
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-medium">M2 V2 cohort analytics (not yet available)</p>
          <p className="text-xs text-muted-foreground">
            Institutional M2 V2 (Next-Semester Performance Prediction) aggregate statistics are
            unavailable because the backend exposes M2 V2 per-student only, with no cohort endpoint
            and no persistence wiring. The validated M2 V2 predictions are surfaced per student for
            the Student and Faculty/Mentor experiences. Additionally, the current cohort is in the
            final / internship semester and has no upcoming regular academic semester, so their
            per-student M2 V2 predictions are NO_DATA by design. No aggregate figures are shown here
            to avoid presenting unverified statistics.
          </p>
        </div>
      </div>

      {/* M3 V2 availability notice — documented limitation, never fabricated */}
      <div className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-3">
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-medium">M3 V2 at-risk cohort analytics (not yet available)</p>
          <p className="text-xs text-muted-foreground">
            Institutional M3 V2 (At-Risk Student Prediction) aggregate risk statistics are
            unavailable for the same reason as M1/M2 V2: the backend exposes M3 V2 per-student only,
            with no cohort endpoint and no persistence wiring. The validated M3 V2 at-risk estimate
            is surfaced per student for the Student and Faculty/Mentor experiences. The current
            cohort is in the final / internship semester with no upcoming regular academic semester,
            so their per-student M3 V2 estimates are NO_DATA by design and must not be fabricated.
            No aggregate figures are shown here to avoid presenting unverified statistics.
          </p>
        </div>
      </div>

      {/* M1 & M2 Header KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Subject Predictions (M1)"
          value={String(m1.total_subject_predictions)}
          icon={BookOpen}
          hint="M1 predicted end-sem subject marks"
        />
        <StatCard
          label="Predicted Avg End-Sem Mark"
          value={m1AvgMarkStr}
          icon={GraduationCap}
          hint="Overall predicted subject performance (/70)"
        />
        <StatCard
          label="Predicted Next-Sem SGPA (M2)"
          value={m2AvgSgpaStr}
          icon={TrendingUp}
          hint="Institution forecast next-semester SGPA"
        />
        <StatCard
          label="Predicted Next-Sem % (M2)"
          value={m2AvgPctStr}
          icon={TrendingUp}
          hint="Institution forecast next-semester percentage"
        />
      </div>

      {/* M1: Subjects Needing Attention Table */}
      <ChartCard
        title="Subjects Needing Attention (M1 Model Forecast)"
        subtitle="Subjects with lowest predicted average end-semester marks (/70)"
        status={m1.subjects_needing_attention.length > 0 ? "ready" : "empty"}
        emptyIcon={Info}
        emptyTitle="No Subject Prediction Data"
        emptyDescription="No M1 subject predictions found for current scope."
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border text-muted-foreground font-semibold">
                <th className="pb-2 pl-1">Subject Code</th>
                <th className="pb-2">Subject Name</th>
                <th className="pb-2">Department</th>
                <th className="pb-2 text-right">Predicted Avg Mark</th>
                <th className="pb-2 pr-1 text-right">Students</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {m1.subjects_needing_attention.map((sub) => (
                <tr key={`${sub.subject_code}-${sub.department_name}`}>
                  <td className="py-2.5 pl-1 font-mono font-medium text-foreground">
                    {sub.subject_code}
                  </td>
                  <td className="py-2.5 text-foreground">{sub.subject_name}</td>
                  <td className="py-2.5 text-muted-foreground">{sub.department_name}</td>
                  <td className="py-2.5 text-right font-medium text-amber-600 dark:text-amber-400">
                    {sub.predicted_avg_mark.toFixed(1)} / 70
                  </td>
                  <td className="py-2.5 pr-1 text-right text-muted-foreground">
                    {sub.students_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartCard>

      {/* M2: SGPA Distribution & Percentage Distribution */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Predicted Next-Semester SGPA Distribution (M2)"
          subtitle="Forecast SGPA distribution for next semester"
          status={hasM2Data && m2.sgpa_distribution.length > 0 ? "ready" : "empty"}
          emptyIcon={Info}
          emptyTitle="No SGPA Distribution Data"
          emptyDescription="No M2 next-semester predictions found for current scope."
        >
          <div className="space-y-3">
            {m2.sgpa_distribution.map((dist) => {
              const pct = sgpaTotal > 0 ? (dist.count / sgpaTotal) * 100 : 0
              return (
                <div key={dist.band} className="space-y-1">
                  <div className="flex justify-between text-xs font-medium">
                    <span>Band: {dist.band}</span>
                    <span className="text-muted-foreground">{dist.count} student(s)</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
          <p className="mt-4 text-xs text-muted-foreground">{m2.disclaimer}</p>
        </ChartCard>

        <ChartCard
          title="Predicted Next-Semester Percentage Distribution (M2)"
          subtitle="Forecast percentage band distribution for next semester"
          status={hasM2Data && m2.percentage_distribution.length > 0 ? "ready" : "empty"}
          emptyIcon={Info}
          emptyTitle="No Percentage Distribution Data"
          emptyDescription="No M2 next-semester percentage predictions found for current scope."
        >
          <div className="space-y-3">
            {m2.percentage_distribution.map((dist) => {
              const pct = pctTotal > 0 ? (dist.count / pctTotal) * 100 : 0
              return (
                <div key={dist.band} className="space-y-1">
                  <div className="flex justify-between text-xs font-medium">
                    <span>Band: {dist.band}</span>
                    <span className="text-muted-foreground">{dist.count} student(s)</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
          <p className="mt-4 text-xs text-muted-foreground">{m2.disclaimer}</p>
        </ChartCard>
      </div>

      {/* M2: Department Performance Forecast */}
      <ChartCard
        title="Department Next-Sem Performance Forecast (M2)"
        subtitle="Predicted average SGPA and Percentage per department"
        status={m2.department_performance_distribution.length > 0 ? "ready" : "empty"}
      >
        <div className="space-y-3">
          {m2.department_performance_distribution.map((dept) => (
            <div
              key={dept.department_code}
              className="flex items-center justify-between text-xs border-b border-border/50 pb-2 last:border-0 last:pb-0"
            >
              <div>
                <p className="font-medium text-foreground">{dept.department_name}</p>
              </div>
              <div className="text-right flex items-center gap-4">
                <div>
                  <span className="text-muted-foreground">SGPA: </span>
                  <span className="font-semibold text-foreground">
                    {dept.predicted_avg_sgpa !== null ? dept.predicted_avg_sgpa.toFixed(2) : "—"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">%: </span>
                  <span className="font-semibold text-foreground">
                    {dept.predicted_avg_percentage !== null
                      ? `${dept.predicted_avg_percentage.toFixed(1)}%`
                      : "—"}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </ChartCard>
    </div>
  )
}
