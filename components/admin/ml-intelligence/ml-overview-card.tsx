"use client"

import { Brain, Cpu, Database, Users, CheckCircle2, AlertCircle } from "lucide-react"
import type { MlOverviewKpis } from "@/lib/admin-api"
import { StatCard } from "@/components/shared/data/stat-card"

export function MlOverviewCard({ kpis }: { kpis: MlOverviewKpis }) {
  const hasPredictions = kpis.total_predictions > 0
  const coverageStr =
    hasPredictions &&
    kpis.coverage_percentage !== null &&
    kpis.coverage_percentage !== undefined
      ? `${kpis.coverage_percentage.toFixed(1)}%`
      : "—"

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-foreground">
            ML Coverage & Active Engines
          </h2>
          <p className="text-xs text-muted-foreground">
            Institution prediction coverage across M1-M4 models
          </p>
        </div>
        <div className="flex items-center gap-2">
          {Object.entries(kpis.models_status).map(([modelKey, status]) => (
            <span
              key={modelKey}
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border ${
                status === "active"
                  ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400"
                  : "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400"
              }`}
            >
              {status === "active" ? (
                <CheckCircle2 className="size-3 text-emerald-500" />
              ) : (
                <AlertCircle className="size-3 text-amber-500" />
              )}
              {modelKey.toUpperCase()} {status === "active" ? "Active" : "No Data"}
            </span>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Students in Scope"
          value={String(kpis.total_students)}
          icon={Users}
          hint="Total students in active query scope"
        />
        <StatCard
          label="Students Evaluated"
          value={String(kpis.students_with_predictions)}
          icon={Brain}
          hint="Students with active ML/rule predictions"
        />
        <StatCard
          label="Prediction Coverage"
          value={coverageStr}
          icon={Cpu}
          hint="Institution coverage ratio"
        />
        <StatCard
          label="Total Predictions"
          value={String(kpis.total_predictions)}
          icon={Database}
          hint="Evaluated prediction records across M1-M4"
        />
      </div>
    </div>
  )
}
