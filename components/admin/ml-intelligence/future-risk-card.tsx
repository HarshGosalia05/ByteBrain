"use client"

import { AlertOctagon, AlertTriangle, ShieldCheck, Info } from "lucide-react"
import type { FutureRiskIntelligence } from "@/lib/admin-api"
import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"

export function FutureRiskCard({ data }: { data: FutureRiskIntelligence }) {
  const hasM3Data = data.future_at_risk_count + data.future_low_risk_count > 0
  const riskPctStr =
    data.future_at_risk_percentage !== null && data.future_at_risk_percentage !== undefined
      ? `${data.future_at_risk_percentage.toFixed(1)}%`
      : "—"

  return (
    <div className="flex flex-col gap-4">
      {/* Header with strict distinction notice */}
      <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4 text-xs text-indigo-950 dark:text-indigo-200">
        <div className="flex items-center gap-2 font-semibold text-sm text-indigo-900 dark:text-indigo-300">
          <AlertOctagon className="size-4 text-indigo-600 dark:text-indigo-400" />
          <span>END-TERM RISK PREDICTION (M3 v3 ML Model)</span>
          <span className="ml-auto rounded-md bg-indigo-500/20 px-2 py-0.5 text-xs text-indigo-700 dark:text-indigo-300">
            ML Forecast (Mid-Sem → End-Term)
          </span>
        </div>

        <p className="mt-1 text-muted-foreground">{data.disclaimer}</p>
      </div>

      {/* Side-by-side KPI comparison: M3 Future Risk vs Current Deterministic Risk Register */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Predicted Future At-Risk"
          value={hasM3Data ? String(data.future_at_risk_count) : "—"}
          icon={AlertOctagon}
          hint={
            hasM3Data
              ? "M3 v3 ML forecast for same-semester end-term academic risk"
              : "No M3 prediction data for current scope"
          }
        />
        <StatCard
          label="Future Risk Ratio"
          value={riskPctStr}
          icon={AlertTriangle}
          hint="Percentage of evaluated students predicted at risk"
        />
        <StatCard
          label="Predicted Low Risk"
          value={hasM3Data ? String(data.future_low_risk_count) : "—"}
          icon={ShieldCheck}
          hint={
            hasM3Data
              ? "Students predicted safe for current semester end-term"
              : "No M3 prediction data for current scope"
          }
        />
        <StatCard
          label="Current Risk Register"
          value={String(data.current_deterministic_high_critical_count)}
          icon={AlertTriangle}
          hint="Deterministic current risk status (risk_predictions table)"
        />
      </div>

      {/* Department & Semester Breakdowns */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="End-Term Risk by Department (M3 v3 ML Model)"
          subtitle="Count and percentage of same-semester end-term risk forecasts per department"
          status={data.future_risk_by_department.length > 0 ? "ready" : "empty"}
          emptyIcon={Info}
          emptyTitle="No Department Risk Data"
          emptyDescription="No department M3 predictions found for current scope."
        >
          <div className="space-y-3">
            {data.future_risk_by_department.map((dept) => (
              <div
                key={dept.department_code}
                className="flex items-center justify-between text-xs border-b border-border/50 pb-2 last:border-0 last:pb-0"
              >
                <div>
                  <p className="font-medium text-foreground">{dept.department_name}</p>
                  <p className="text-muted-foreground">
                    {dept.future_risk_count} of {dept.total_students} student(s) forecast at risk
                  </p>
                </div>
                <div className="text-right">
                  <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                    {dept.risk_percentage !== null ? `${dept.risk_percentage.toFixed(1)}%` : "—"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </ChartCard>

        <ChartCard
          title="End-Term Risk by Semester (M3 v3 ML Model)"
          subtitle="Same-semester end-term risk forecast broken down by student semester"

          status={data.future_risk_by_semester.length > 0 ? "ready" : "empty"}
          emptyIcon={Info}
          emptyTitle="No Semester Risk Data"
          emptyDescription="No semester M3 predictions found for current scope."
        >
          <div className="space-y-3">
            {data.future_risk_by_semester.map((sem) => (
              <div
                key={sem.semester_no}
                className="flex items-center justify-between text-xs border-b border-border/50 pb-2 last:border-0 last:pb-0"
              >
                <div>
                  <p className="font-medium text-foreground">Semester {sem.semester_no}</p>
                  <p className="text-muted-foreground">
                    {sem.future_risk_count} of {sem.total_students} student(s) forecast at risk
                  </p>
                </div>
                <div className="text-right">
                  <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                    {sem.risk_percentage !== null ? `${sem.risk_percentage.toFixed(1)}%` : "—"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </ChartCard>
      </div>
    </div>
  )
}
