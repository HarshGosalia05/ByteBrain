"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  BatteryCharging,
  BookOpen,
  BookMarked,
  Clock,
  Cpu,
  Gauge,
  GitCompareArrows,
  GraduationCap,
  Scale,
  ShieldCheck,
  UserCheck,
  Users,
  Zap,
} from "lucide-react"

import type { PerformanceKpi, WorkloadSummary } from "@/lib/faculty-api"

import { SoSDelta } from "@/components/faculty/performance/sos-delta"
import { StatCard, type StatCardTone } from "@/components/shared/data/stat-card"

function kpiTone(kpi: PerformanceKpi, thresholds: WorkloadSummary["thresholds"]): StatCardTone {
  switch (kpi.key) {
    case "utilization_pct":
      if (kpi.value === null) return "primary"
      if (kpi.value >= thresholds.overload_threshold * 100) return "destructive"
      if (kpi.value < thresholds.underutilized_threshold * 100) return "warning"
      return "success"
    case "balance_score":
    case "coverage_pct":
      if (kpi.value === null) return "primary"
      return kpi.value < thresholds.balance_watch ? "warning" : "success"
    case "remaining_capacity":
      return kpi.value !== null && kpi.value <= 0 ? "destructive" : "primary"
    case "resource_score":
    case "efficiency_score":
      if (kpi.value === null) return "primary"
      if (kpi.value >= thresholds.health_good) return "success"
      if (kpi.value >= thresholds.health_watch) return "warning"
      return "destructive"
    default:
      return "primary"
  }
}

function kpiIcon(key: string) {
  switch (key) {
    case "subjects":
      return BookOpen
    case "students":
      return Users
    case "credits":
    case "credit_load":
      return BookMarked
    case "offerings":
      return GraduationCap
    case "weekly_hours":
      return Clock
    case "utilization_pct":
      return Gauge
    case "remaining_capacity":
      return BatteryCharging
    case "balance_score":
      return Scale
    case "coverage_pct":
      return ShieldCheck
    case "diversity_index":
      return GitCompareArrows
    case "theory_practical":
      return Scale
    case "avg_students_per_subject":
      return Users
    case "efficiency_score":
      return Zap
    case "resource_score":
      return Cpu
    case "mentee_overlap":
      return UserCheck
    default:
      return Gauge
  }
}

function kpiAnchor(key: string): string {
  switch (key) {
    case "students":
    case "avg_students_per_subject":
      return "students"
    case "resource_score":
    case "mentee_overlap":
    case "coverage_pct":
      return "governance"
    default:
      return "workload-charts"
  }
}

export function WorkloadView({
  data,
  children,
}: {
  data: WorkloadSummary
  children?: React.ReactNode
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const handleKpiClick = (kpi: PerformanceKpi) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}#${kpiAnchor(kpi.key)}`)
  }

  return (
    <div className="flex flex-col gap-6">
      <section
        className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
        aria-label="Executive workload KPIs"
      >
        {data.kpis.map((kpi, index) => (
          <button
            key={`${kpi.key}-${index}`}
            type="button"
            onClick={() => handleKpiClick(kpi)}
            className="text-left transition-opacity hover:opacity-80"
            aria-label={`${kpi.label}: ${kpi.display}. Click to drill down.`}
          >
            <StatCard
              label={kpi.label}
              value={kpi.display}
              icon={kpiIcon(kpi.key)}
              tone={kpiTone(kpi, data.thresholds)}
              hint={
                <SoSDelta
                  delta={kpi.delta}
                  hasPrevious={kpi.has_previous}
                  previousDisplay={kpi.previous_display}
                />
              }
            />
          </button>
        ))}
      </section>

      {children}
    </div>
  )
}
