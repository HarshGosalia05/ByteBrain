"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  Award,
  BadgeCheck,
  BookOpen,
  CalendarCheck,
  Gauge,
  TriangleAlert,
  UserX,
  Users,
} from "lucide-react"

import type { PerformanceKpi, PerformanceSummary } from "@/lib/faculty-api"

import { StatCard, type StatCardTone } from "@/components/shared/data/stat-card"

import { SoSDelta } from "./sos-delta"

function kpiTone(kpi: PerformanceKpi): StatCardTone {
  switch (kpi.key) {
    case "below_count":
      return kpi.value && kpi.value > 0 ? "destructive" : "success"
    case "ineligible_count":
      return kpi.value && kpi.value > 0 ? "warning" : "success"
    case "pass_rate":
      return "success"
    default:
      return "primary"
  }
}

function kpiIcon(key: string) {
  switch (key) {
    case "subjects":
      return BookOpen
    case "enrollments":
      return Users
    case "avg_performance":
      return Gauge
    case "avg_attendance":
      return CalendarCheck
    case "pass_rate":
      return BadgeCheck
    case "distinction_count":
      return Award
    case "below_count":
      return TriangleAlert
    case "ineligible_count":
      return UserX
    default:
      return Gauge
  }
}

function kpiAnchor(key: string): string {
  switch (key) {
    case "avg_performance":
    case "avg_attendance":
    case "pass_rate":
    case "subjects":
      return "performance-charts"
    case "distinction_count":
    case "below_count":
    case "ineligible_count":
      return "learning-gaps"
    default:
      return "students"
  }
}

export function PerformanceView({
  data,
  children,
}: {
  data: PerformanceSummary
  children?: React.ReactNode
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const handleKpiClick = (kpi: PerformanceKpi) => {
    const params = new URLSearchParams(searchParams.toString())
    if (kpi.key === "ineligible_count" || kpi.key === "below_count") {
      params.delete("gap_status")
      params.set("page", "1")
    }
    router.push(`${pathname}?${params.toString()}#${kpiAnchor(kpi.key)}`)
  }

  return (
    <div className="flex flex-col gap-6">
      <section
        className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
        aria-label="Executive performance KPIs"
      >
        {data.kpis.map((kpi) => (
          <button
            key={kpi.key}
            type="button"
            onClick={() => handleKpiClick(kpi)}
            className="text-left transition-opacity hover:opacity-80"
            aria-label={`${kpi.label}: ${kpi.display}. Click to drill down.`}
          >
            <StatCard
              label={kpi.label}
              value={kpi.display}
              icon={kpiIcon(kpi.key)}
              tone={kpiTone(kpi)}
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
