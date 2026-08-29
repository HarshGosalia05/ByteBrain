"use client"

import { Brain, Cpu, Database, Users, CheckCircle2, AlertCircle, ShieldAlert } from "lucide-react"
import type { MlOverviewKpis } from "@/lib/admin-api"
import { StatCard } from "@/components/shared/data/stat-card"

function statusLabel(modelKey: string, status: string) {
  if (status === "active") return `${modelKey.toUpperCase()} Active`
  if (status === "blocked") return `${modelKey.toUpperCase()} Blocked`
  return `${modelKey.toUpperCase()} No Data`
}

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
            ML Coverage & Model Status
          </h2>
          <p className="text-xs text-muted-foreground">
            Institution prediction coverage and production validation status across M1-M4
          </p>
        </div>
        <div className="flex items-center gap-2">
          {Object.entries(kpis.models_status).map(([modelKey, status]) => (
            <span
              key={modelKey}
              title={status === "blocked" ? "Validation gate not satisfied" : undefined}
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border ${
                status === "active"
                  ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400"
                  : status === "blocked"
                    ? "bg-red-500/10 text-red-600 border-red-500/20 dark:text-red-400"
                    : "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400"
              }`}
            >
              {status === "active" ? (
                <CheckCircle2 className="size-3 text-emerald-500" />
              ) : status === "blocked" ? (
                <ShieldAlert className="size-3 text-red-500" />
              ) : (
                <AlertCircle className="size-3 text-amber-500" />
              )}
              {statusLabel(modelKey, status)}
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
