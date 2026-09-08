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

  const m2AvgTheoryStr =
    m2.predicted_avg_theory_pct !== null && m2.predicted_avg_theory_pct !== undefined
      ? `${m2.predicted_avg_theory_pct.toFixed(1)}%`
      : "—"

  const m2AvgPracticalStr =
    m2.predicted_avg_practical_pct !== null && m2.predicted_avg_practical_pct !== undefined
      ? `${m2.predicted_avg_practical_pct.toFixed(1)}%`
      : "—"

  const hasM2Data = m2.department_performance_distribution.length > 0
  const theoryTotal = m2.theory_distribution.reduce((sum, d) => sum + d.count, 0)
  const practicalTotal = m2.practical_distribution.reduce((sum, d) => sum + d.count, 0)

  return (
    <div className="flex flex-col gap-6">
      {/* Clean M1 V3 availability notice — documented limitation, never fabricated */}
      <div className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-3">
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-medium">Clean M1 V3 cohort analytics (surfaced per-student)</p>
          <p className="text-xs text-muted-foreground">
            Institutional Clean M1 V3 (Subject Marks Prediction) predictions are surfaced per student for the
            Student, Faculty/Mentor, and Chatbot experiences with 38-feature history learning. No unverified
            aggregate figures are displayed here to ensure honest generalization.
          </p>
        </div>
      </div>

      {/* M2-TP availability notice — documented limitation, never fabricated */}
      <div className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-3">
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-medium">M2-TP cohort analytics (validated M2-TP aggregate)</p>
          <p className="text-xs text-muted-foreground">
            The M2-TP (Next-Semester Theory & Practical Performance) aggregate below is computed from
            persisted, model-version-verified M2-TP predictions (prediction_type=&quot;m2&quot;,
            model_version=&quot;m2_tp_v1&quot;). Only verified rows are aggregated; old or
            non-M2-TP rows are never mixed in. Forecasts apply to upcoming regular semesters and are
            never fabricated.
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
          label="Predicted Next-Sem Theory (M2)"
          value={m2AvgTheoryStr}
          icon={TrendingUp}
          hint="Institution forecast next-semester Theory %"
        />
        <StatCard
          label="Predicted Next-Sem Practical (M2)"
          value={m2AvgPracticalStr}
          icon={TrendingUp}
          hint="Institution forecast next-semester Practical %"
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

      {/* M2: Theory Distribution & Practical Distribution */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Predicted Next-Semester Theory Distribution (M2)"
          subtitle="Forecast Theory percentage band distribution for next semester"
          status={hasM2Data && m2.theory_distribution.length > 0 ? "ready" : "empty"}
          emptyIcon={Info}
          emptyTitle="No Theory Distribution Data"
          emptyDescription="No M2-TP next-semester predictions found for current scope."
        >
          <div className="space-y-3">
            {m2.theory_distribution.map((dist) => {
              const pct = theoryTotal > 0 ? (dist.count / theoryTotal) * 100 : 0
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
          title="Predicted Next-Semester Practical Distribution (M2)"
          subtitle="Forecast Practical percentage band distribution for next semester"
          status={hasM2Data && m2.practical_distribution.length > 0 ? "ready" : "empty"}
          emptyIcon={Info}
          emptyTitle="No Practical Distribution Data"
          emptyDescription="No M2-TP next-semester practical predictions found for current scope."
        >
          <div className="space-y-3">
            {m2.practical_distribution.map((dist) => {
              const pct = practicalTotal > 0 ? (dist.count / practicalTotal) * 100 : 0
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
        subtitle="Predicted average Theory and Practical percentage per department"
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
                  <span className="text-muted-foreground">Theory: </span>
                  <span className="font-semibold text-foreground">
                    {dept.predicted_avg_theory_pct !== null
                      ? `${dept.predicted_avg_theory_pct.toFixed(1)}%`
                      : "—"}
                  </span>
                </div>
                {dept.predicted_avg_practical_pct !== null && dept.predicted_avg_practical_pct !== undefined && (
                  <div>
                    <span className="text-muted-foreground">Practical: </span>
                    <span className="font-semibold text-foreground">
                      {dept.predicted_avg_practical_pct.toFixed(1)}%
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </ChartCard>
    </div>
  )
}
