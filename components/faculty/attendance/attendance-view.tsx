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

import type { AttendanceSummary, PerformanceKpi } from "@/lib/faculty-api"

import { SoSDelta } from "@/components/faculty/performance/sos-delta"
import { StatCard, type StatCardTone } from "@/components/shared/data/stat-card"

function kpiTone(kpi: PerformanceKpi): StatCardTone {
  switch (kpi.key) {
    case "below_count":
      return kpi.value && kpi.value > 0 ? "destructive" : "success"
    case "ineligible_count":
      return kpi.value && kpi.value > 0 ? "warning" : "success"
    case "lowest_subject":
      return "warning"
    case "highest_subject":
    case "above_count":
    case "compliance_pct":
      return "success"
    default:
      return "primary"
  }
}

function kpiIcon(key: string) {
  switch (key) {
    case "overall_attendance":
    case "avg_attendance":
      return Gauge
    case "highest_subject":
      return Award
    case "lowest_subject":
    case "below_count":
      return TriangleAlert
    case "above_count":
    case "compliance_pct":
      return BadgeCheck
    case "ineligible_count":
      return UserX
    case "avg_total_classes":
      return BookOpen
    case "attendance_records":
      return Users
    default:
      return CalendarCheck
  }
}

function kpiAnchor(key: string): string {
  switch (key) {
    case "ineligible_count":
      return "governance"
    case "attendance_records":
      return "students"
    default:
      return "attendance-charts"
  }
}

export function AttendanceView({
  data,
  children,
}: {
  data: AttendanceSummary
  children?: React.ReactNode
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const handleKpiClick = (kpi: PerformanceKpi) => {
    const params = new URLSearchParams(searchParams.toString())
    if (kpi.key === "ineligible_count" || kpi.key === "below_count") {
      params.delete("band")
      params.delete("defaulter_status")
      params.set("page", "1")
    }
    router.push(`${pathname}?${params.toString()}#${kpiAnchor(kpi.key)}`)
  }

  return (
    <div className="flex flex-col gap-6">
      <section
        className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
        aria-label="Executive attendance KPIs"
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
