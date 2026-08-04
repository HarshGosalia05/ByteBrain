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

export function PerformanceView({ data }: { data: PerformanceSummary }) {
  return (
    <div className="flex flex-col gap-6">
      <section
        className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
        aria-label="Executive performance KPIs"
      >
        {data.kpis.map((kpi) => (
          <StatCard
            key={kpi.key}
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
        ))}
      </section>
    </div>
  )
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
