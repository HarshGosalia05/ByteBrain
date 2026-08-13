"use client"

import { Rocket, CheckCircle, AlertTriangle, Cpu, Info } from "lucide-react"
import type { CareerReadinessIntelligence } from "@/lib/admin-api"
import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"

export function CareerReadinessCard({ data }: { data: CareerReadinessIntelligence }) {
  const hasM4Data = data.department_readiness_distribution.length > 0
  const avgScoreStr =
    data.avg_career_readiness_score !== null && data.avg_career_readiness_score !== undefined
      ? `${data.avg_career_readiness_score.toFixed(1)} / 100`
      : "—"

  return (
    <div className="flex flex-col gap-4">
      {/* Header notice explicitly declaring M4 is rule-based */}
      <div className="rounded-xl border border-teal-500/20 bg-teal-500/5 p-4 text-xs text-teal-950 dark:text-teal-200">
        <div className="flex items-center gap-2 font-semibold text-sm text-teal-900 dark:text-teal-300">
          <Cpu className="size-4 text-teal-600 dark:text-teal-400" />
          <span>M4 CAREER READINESS ENGINE</span>
          <span className="ml-auto rounded-md bg-teal-500/20 px-2 py-0.5 text-xs text-teal-700 dark:text-teal-300">
            Deterministic Rule-Based Engine (NOT ML)
          </span>
        </div>
        <p className="mt-1 text-muted-foreground">{data.disclaimer}</p>
      </div>

      {/* KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Avg Career Readiness"
          value={avgScoreStr}
          icon={Rocket}
          hint="Institution deterministic readiness score"
        />
        <StatCard
          label="High Readiness (>=75)"
          value={hasM4Data ? String(data.readiness_level_counts.High ?? 0) : "—"}
          icon={CheckCircle}
          hint={
            hasM4Data
              ? "Students meeting High readiness thresholds"
              : "No M4 readiness data for current scope"
          }
        />
        <StatCard
          label="Medium Readiness (50-74)"
          value={hasM4Data ? String(data.readiness_level_counts.Medium ?? 0) : "—"}
          icon={Info}
          hint={
            hasM4Data
              ? "Students in Medium readiness band"
              : "No M4 readiness data for current scope"
          }
        />
        <StatCard
          label="Low Readiness (<50)"
          value={hasM4Data ? String(data.readiness_level_counts.Low ?? 0) : "—"}
          icon={AlertTriangle}
          hint={
            hasM4Data
              ? "Students flagged for career readiness support"
              : "No M4 readiness data for current scope"
          }
        />
      </div>

      {/* Department Distribution & Factors */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Department Career Readiness (M4 Rule Engine)"
          subtitle="Average score and level distribution per department"
          status={data.department_readiness_distribution.length > 0 ? "ready" : "empty"}
        >
          <div className="space-y-3">
            {data.department_readiness_distribution.map((dept) => (
              <div
                key={dept.department_code}
                className="flex items-center justify-between text-xs border-b border-border/50 pb-2 last:border-0 last:pb-0"
              >
                <div>
                  <p className="font-medium text-foreground">{dept.department_name}</p>
                  <p className="text-muted-foreground">
                    High: {dept.high_count} | Medium: {dept.medium_count} | Low: {dept.low_count}
                  </p>
                </div>
                <div className="text-right font-semibold text-teal-600 dark:text-teal-400">
                  {dept.avg_score !== null ? `${dept.avg_score.toFixed(1)} / 100` : "—"}
                </div>
              </div>
            ))}
          </div>
        </ChartCard>

        <ChartCard
          title="Primary Drivers & Risk Factors (M4 Grounded)"
          subtitle="Top aggregated positive drivers and risk factors across students"
          status={
            data.top_positive_factors.length > 0 || data.top_risk_factors.length > 0
              ? "ready"
              : "empty"
          }
        >
          <div className="space-y-4 text-xs">
            <div>
              <p className="font-semibold text-emerald-600 dark:text-emerald-400 mb-2 flex items-center gap-1.5">
                <CheckCircle className="size-3.5" /> Top Positive Drivers
              </p>
              <div className="space-y-1.5">
                {data.top_positive_factors.map((item) => (
                  <div
                    key={item.factor}
                    className="flex justify-between rounded-md bg-emerald-500/5 px-2.5 py-1.5"
                  >
                    <span>{item.factor}</span>
                    <span className="font-mono font-medium text-muted-foreground">
                      {item.frequency} student(s)
                    </span>
                  </div>
                ))}
                {data.top_positive_factors.length === 0 && (
                  <p className="text-muted-foreground">No positive drivers recorded.</p>
                )}
              </div>
            </div>

            <div>
              <p className="font-semibold text-amber-600 dark:text-amber-400 mb-2 flex items-center gap-1.5">
                <AlertTriangle className="size-3.5" /> Top Risk Factors
              </p>
              <div className="space-y-1.5">
                {data.top_risk_factors.map((item) => (
                  <div
                    key={item.factor}
                    className="flex justify-between rounded-md bg-amber-500/5 px-2.5 py-1.5"
                  >
                    <span>{item.factor}</span>
                    <span className="font-mono font-medium text-muted-foreground">
                      {item.frequency} student(s)
                    </span>
                  </div>
                ))}
                {data.top_risk_factors.length === 0 && (
                  <p className="text-muted-foreground">No risk factors recorded.</p>
                )}
              </div>
            </div>
          </div>
        </ChartCard>
      </div>
    </div>
  )
}
