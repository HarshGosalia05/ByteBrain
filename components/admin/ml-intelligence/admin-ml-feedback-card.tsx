"use client"

import { ClipboardCheck } from "lucide-react"
import type { AdminMlFeedbackHealth } from "@/lib/admin-api"
import { ChartCard } from "@/components/shared/data/chart-card"

function Kpi({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone?: "default" | "success" | "warning" | "destructive"
}) {
  const toneClass =
    tone === "success"
      ? "text-chart-2 dark:text-chart-2"
      : tone === "warning"
        ? "text-chart-3 dark:text-chart-3"
        : tone === "destructive"
          ? "text-destructive"
          : "text-foreground"
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-border p-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-2xl font-bold ${toneClass}`}>{value}</span>
    </div>
  )
}

export function AdminMlFeedbackCard({ health }: { health: AdminMlFeedbackHealth }) {
  return (
    <ChartCard
      title="Faculty Feedback on Future-Risk Predictions"
      subtitle="ML-12 §12.5 health indicator — volume and distribution of faculty reviews (latest verdict wins)"
      status="ready"
    >
      <div className="flex flex-col gap-5">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Reviewed predictions" value={health.total} />
          <Kpi label="Confirmed" value={health.confirmed} tone="success" />
          <Kpi label="Dismissed" value={health.dismissed} tone="destructive" />
          <Kpi label="Awaiting review" value={health.pending} tone="warning" />
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <div className="flex flex-col gap-2">
            <p className="text-[0.6875rem] font-semibold tracking-widest text-muted-foreground uppercase">
              By department
            </p>
            {health.by_department.length === 0 ? (
              <p className="text-xs text-muted-foreground">No reviews recorded yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground">
                    <th className="pb-1 pr-3 font-medium">Department</th>
                    <th className="pb-1 pr-3 text-right font-medium">Reviewed</th>
                    <th className="pb-1 pr-3 text-right font-medium">Confirmed</th>
                    <th className="pb-1 text-right font-medium">Dismissed</th>
                  </tr>
                </thead>
                <tbody>
                  {health.by_department.map((dept) => (
                    <tr key={dept.department_code} className="border-t border-border">
                      <td className="py-1.5 pr-3">{dept.department_name}</td>
                      <td className="py-1.5 pr-3 text-right">{dept.reviewed}</td>
                      <td className="py-1.5 pr-3 text-right">{dept.confirmed}</td>
                      <td className="py-1.5 text-right">{dept.dismissed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <p className="text-[0.6875rem] font-semibold tracking-widest text-muted-foreground uppercase">
              By semester
            </p>
            {health.by_semester.length === 0 ? (
              <p className="text-xs text-muted-foreground">No reviews recorded yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground">
                    <th className="pb-1 pr-3 font-medium">Semester</th>
                    <th className="pb-1 pr-3 text-right font-medium">Reviewed</th>
                    <th className="pb-1 pr-3 text-right font-medium">Confirmed</th>
                    <th className="pb-1 text-right font-medium">Dismissed</th>
                  </tr>
                </thead>
                <tbody>
                  {health.by_semester.map((sem) => (
                    <tr key={String(sem.semester_no)} className="border-t border-border">
                      <td className="py-1.5 pr-3">
                        {sem.semester_no === null ? "—" : `Semester ${sem.semester_no}`}
                      </td>
                      <td className="py-1.5 pr-3 text-right">{sem.reviewed}</td>
                      <td className="py-1.5 pr-3 text-right">{sem.confirmed}</td>
                      <td className="py-1.5 text-right">{sem.dismissed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
          <ClipboardCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {health.disclaimer}
        </p>
      </div>
    </ChartCard>
  )
}
