"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { FilterX, Sparkles } from "lucide-react"

import type { AdminMlIntelligenceData } from "@/lib/admin-api"
import { getDepartmentBatches } from "@/lib/batch-utils"
import { MlOverviewCard } from "./ml-overview-card"
import { FutureRiskCard } from "./future-risk-card"
import { AcademicPredictionCard } from "./academic-prediction-card"
import { CareerReadinessCard } from "./career-readiness-card"
import { GroundedInsightsCard } from "./grounded-insights-card"
import { AdminGenerationPanel } from "./admin-generation-panel"

const selectClassName =
  "h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-xs focus:outline-none focus:ring-2 focus:ring-ring"

export function AdminMlIntelligenceGrid({ data }: { data: AdminMlIntelligenceData }) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const batch = searchParams.get("batch") || searchParams.get("academic_year") || ""
  const departmentCode = searchParams.get("department_code") || ""
  const semester = searchParams.get("semester") || ""

  const handleFilterChange = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (key === "batch") {
      if (value) {
        params.set("batch", value)
        params.delete("academic_year")
      } else {
        params.delete("batch")
        params.delete("academic_year")
      }
    } else if (key === "department_code") {
      if (value) {
        params.set("department_code", value)
        const targetBatches = getDepartmentBatches(value, data.filter_options)
        const curBatch = params.get("batch") || params.get("academic_year")
        if (curBatch && !targetBatches.includes(curBatch)) {
          params.delete("batch")
          params.delete("academic_year")
        }
      } else {
        params.delete("department_code")
      }
    } else {
      if (value) {
        params.set(key, value)
      } else {
        params.delete(key)
      }
    }
    router.push(`${pathname}?${params.toString()}`)
  }

  const handleResetFilters = () => {
    router.push(pathname)
  }

  const activeFiltersCount = (batch ? 1 : 0) + (departmentCode ? 1 : 0) + (semester ? 1 : 0)

  const availableBatches = getDepartmentBatches(departmentCode, data.filter_options)

  const hasM3Data =
    data.future_risk.future_at_risk_count + data.future_risk.future_low_risk_count > 0
  const executiveInsights = hasM3Data
    ? data.executive_insights
    : data.executive_insights.filter((insight) => insight.category !== "Future Risk Intelligence")

  return (
    <div className="flex flex-col gap-8 pb-12">
      {/* Page Header & Filter Bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Admin ML Intelligence
            </h1>
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
              <Sparkles className="size-3" /> M1-M4 Academic Intelligence
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Institution-level academic forecasts, same-semester end-term risk predictions, and career readiness analytics
          </p>

        </div>

        {/* Filter Bar */}
        <div className="flex items-center gap-3">
          <select
            className={selectClassName}
            value={batch}
            onChange={(e) => handleFilterChange("batch", e.target.value)}
            aria-label="Starting Batch"
          >
            <option value="">All Starting Batches</option>
            {availableBatches.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>

          <select
            className={selectClassName}
            value={departmentCode}
            onChange={(e) => handleFilterChange("department_code", e.target.value)}
            aria-label="Filter by department"
          >
            <option value="">All Departments</option>
            {data.filter_options.departments.map((dept) => (
              <option key={dept.department_code} value={String(dept.department_code)}>
                {dept.department_name} ({dept.department_code})
              </option>
            ))}
          </select>

          <select
            className={selectClassName}
            value={semester}
            onChange={(e) => handleFilterChange("semester", e.target.value)}
            aria-label="Filter by semester"
          >
            <option value="">All Semesters</option>
            {data.filter_options.semesters.map((sem) => (
              <option key={sem.semester_no} value={String(sem.semester_no)}>
                Semester {sem.semester_no}
              </option>
            ))}
          </select>

          {activeFiltersCount > 0 && (
            <button
              onClick={handleResetFilters}
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <FilterX className="size-3.5" /> Reset
            </button>
          )}
        </div>
      </div>

      {/* Generation controls */}
      <AdminGenerationPanel />

      {/* 1. Overview KPIs & Models Status */}
      <MlOverviewCard kpis={data.overview} />

      {/* 2. M3 Future Risk Intelligence (STRICTLY SEPARATE) */}
      <FutureRiskCard data={data.future_risk} />

      {/* 3. M1 & M2 Academic Prediction Intelligence */}
      <AcademicPredictionCard data={data.academic_predictions} />

      {/* 4. M4 Career Readiness Intelligence (RULE-BASED) */}
      <CareerReadinessCard data={data.career_readiness} />

      {/* 5. Grounded Executive Insights */}
      <GroundedInsightsCard insights={executiveInsights} />
    </div>
  )
}
