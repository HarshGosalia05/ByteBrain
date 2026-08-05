"use client"

import {
  BookMarked,
  Clock,
  Gauge,
  GraduationCap,
  Users,
  Layers,
} from "lucide-react"

import { StatCard } from "@/components/shared/data/stat-card"
import { ErrorState } from "@/components/shared/state/error-state"
import type { WorkloadBenchmark } from "@/lib/faculty-api"
import type { SectionResult } from "@/lib/section-result"

function formatHours(value: number | null): string {
  return value !== null ? `${value.toFixed(1)}h` : "—"
}

export function BenchmarkView({ data }: { data: SectionResult<WorkloadBenchmark> }) {
  const benchmark = data.data

  return (
    <section id="benchmark" className="flex scroll-mt-6 flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Department resource summary</h2>
        <p className="text-sm text-muted-foreground">
          Aggregate figures for your department only — no individual faculty identity or numbers.
        </p>
      </div>

      {data.error ? (
        <ErrorState title="Failed to load department benchmark" description={data.error} />
      ) : benchmark ? (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            <StatCard
              label="Department faculty"
              value={String(benchmark.department_summary.faculty_count)}
              icon={Users}
              tone="primary"
            />
            <StatCard
              label="Total offerings"
              value={String(benchmark.department_summary.total_offerings)}
              icon={BookMarked}
              tone="primary"
            />
            <StatCard
              label="Total credits"
              value={String(benchmark.department_summary.total_credits)}
              icon={Layers}
              tone="primary"
            />
            <StatCard
              label="Total students"
              value={String(benchmark.department_summary.total_students)}
              icon={GraduationCap}
              tone="primary"
            />
            <StatCard
              label="Classes conducted"
              value={String(benchmark.department_summary.total_classes ?? "—")}
              icon={BookMarked}
              tone="primary"
            />
            <StatCard
              label="Department mean weekly hours"
              value={formatHours(benchmark.department_summary.mean_weekly_hours)}
              icon={Clock}
              tone="primary"
            />
            <StatCard
              label="Department mean capacity utilization"
              value={
                benchmark.department_summary.mean_capacity_utilization !== null
                  ? `${benchmark.department_summary.mean_capacity_utilization.toFixed(1)}%`
                  : "—"
              }
              icon={Gauge}
              tone="primary"
            />
          </div>

          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl bg-card px-4 py-3 text-xs text-muted-foreground ring-1 ring-foreground/10">
            <span>
              <span className="font-medium text-foreground">Your position: </span>
              {benchmark.items.length} offering(s) · mean{" "}
              {formatHours(
                benchmark.items.length
                  ? benchmark.items.reduce((acc, i) => acc + (i.weekly_hours ?? 0), 0) /
                      benchmark.items.length
                  : null,
              )}{" "}
              vs department mean{" "}
              {formatHours(benchmark.department_mean_weekly_hours)}
            </span>
            <span>
              {benchmark.department_mean_weekly_hours !== null &&
                (() => {
                  const own =
                    benchmark.items.length
                      ? benchmark.items.reduce((acc, i) => acc + (i.weekly_hours ?? 0), 0) /
                        benchmark.items.length
                      : 0
                  const diff = own - benchmark.department_mean_weekly_hours
                  if (benchmark.items.length === 0) return "No offerings in scope to position."
                  if (diff > 0) return `${diff.toFixed(1)}h above the department aggregate.`
                  if (diff < 0) return `${Math.abs(diff).toFixed(1)}h below the department aggregate.`
                  return "In line with the department aggregate."
                })()}
            </span>
          </div>
        </div>
      ) : null}
    </section>
  )
}
