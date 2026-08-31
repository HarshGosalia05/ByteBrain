"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ArrowDown, ArrowUp, Minus, ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { EmptyState } from "@/components/shared/state/empty-state"
import { ErrorState } from "@/components/shared/state/error-state"
import type { WorkloadGovernance, WorkloadGovernanceItem, WorkloadHealthScore } from "@/lib/faculty-api"
import type { SectionResult } from "@/lib/section-result"
import { cn } from "@/lib/utils"

const MAX_ROWS = 50

const STATUSES = [
  "Overloaded",
  "Underutilized",
  "Balanced",
  "Credit Imbalance",
  "Student Imbalance",
  "Capacity Warning",
  "All",
] as const

type Status = (typeof STATUSES)[number]

function statusVariant(status: string): "destructive" | "warning" | "success" {
  switch (status) {
    case "Overloaded":
      return "destructive"
    case "Balanced":
      return "success"
    default:
      return "warning"
  }
}

function healthVariant(band: string): "destructive" | "warning" | "success" {
  switch (band) {
    case "Excellent":
    case "Good":
      return "success"
    case "Watch":
      return "warning"
    default:
      return "destructive"
  }
}

function GovernanceDelta({
  delta,
  previousDisplay,
  previousReason,
}: {
  delta: number | null
  previousDisplay: string | null
  previousReason: string | null
}) {
  if (delta === null) {
    return (
      <div className="flex flex-col gap-0.5">
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <Minus className="size-3.5" />
          {previousDisplay ?? "—"}
        </span>
        {previousReason && (
          <span className="max-w-56 text-xs text-muted-foreground">{previousReason}</span>
        )}
      </div>
    )
  }
  const up = delta > 0
  return (
    <div className="flex flex-col gap-0.5">
      <span
        className={cn(
          "inline-flex items-center gap-1 text-xs font-medium tabular-nums",
          up ? "text-chart-2" : "text-destructive",
        )}
      >
        {up ? <ArrowUp className="size-3.5" /> : <ArrowDown className="size-3.5" />}
        {up ? `+${delta.toFixed(1)}` : delta.toFixed(1)}
        {previousDisplay && (
          <span className="font-normal text-muted-foreground">vs {previousDisplay}</span>
        )}
      </span>
      {previousReason && (
        <span className="max-w-56 text-xs text-muted-foreground">{previousReason}</span>
      )}
    </div>
  )
}

export function GovernanceView({
  governance,
  healthScore,
}: {
  governance: SectionResult<WorkloadGovernance>
  healthScore: SectionResult<WorkloadHealthScore>
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const activeStatus = (searchParams.get("workload_status") as Status) || "All"

  const selectStatus = (status: Status) => {
    const params = new URLSearchParams(searchParams.toString())
    if (status === "All") {
      params.delete("workload_status")
    } else {
      params.set("workload_status", status)
    }
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}#governance`)
  }

  const handleRowClick = (item: WorkloadGovernanceItem) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("subject_id", item.subject_id)
    params.set("workload_status", item.status)
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}#students`)
  }

  const health = healthScore.data
  const gov = governance.data
  const allItems = gov?.items ?? []
  const shownItems =
    activeStatus === "All" ? allItems : allItems.filter((item) => item.status === activeStatus)
  const capped = shownItems.length > MAX_ROWS
  const visibleItems = shownItems.slice(0, MAX_ROWS)

  return (
    <section id="governance" className="flex scroll-mt-6 flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Governance &amp; workload review</h2>
          <p className="text-sm text-muted-foreground">
            Rule-based workload flags with visible reasons, not predictions.
          </p>
        </div>
        {gov && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="destructive">{gov.overloaded_count} Overloaded</Badge>
            <Badge variant="warning">
              {gov.underutilized_count +
                gov.credit_imbalance_count +
                gov.student_imbalance_count +
                gov.capacity_warning_count}{" "}
              Watch
            </Badge>
            <Badge variant="success">{gov.balanced_count} Balanced</Badge>
          </div>
        )}
      </div>

      {healthScore.error ? (
        <ErrorState title="Failed to load workload health" description={healthScore.error} />
      ) : health ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
            <Badge variant={healthVariant(health.scope_band)} className="capitalize">
              {health.scope_band}
            </Badge>
            <span className="text-2xl font-semibold tabular-nums">
              {health.scope_score !== null ? health.scope_score.toFixed(1) : "—"}
            </span>
            <p className="text-sm text-muted-foreground">{health.scope_reason}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {health.subjects
              .filter((s) => s.subject_id !== null)
              .map((s, idx) => (
                <div key={`${s.subject_id}-${idx}`} className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-mono text-xs text-muted-foreground">{s.subject_code}</p>
                      <p className="truncate text-sm font-medium">{s.subject_name}</p>
                    </div>
                    <Badge variant={healthVariant(s.band)} className="capitalize">
                      {s.band}
                    </Badge>
                  </div>
                  <p className="mt-2 text-2xl font-semibold tabular-nums">
                    {s.score !== null ? s.score.toFixed(1) : "—"}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">{s.reason}</p>
                </div>
              ))}
          </div>
        </div>
      ) : null}

      {governance.error ? (
        <ErrorState title="Failed to load governance" description={governance.error} />
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap items-center gap-1 rounded-md border border-input bg-background p-0.5">
              {STATUSES.map((status) => (
                <button
                  key={status}
                  type="button"
                  className={cn(
                    "h-8 rounded px-2.5 text-sm font-medium transition-colors",
                    activeStatus === status
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                  onClick={() => selectStatus(status)}
                  aria-pressed={activeStatus === status}
                >
                  {status}
                </button>
              ))}
            </div>
          </div>

          {visibleItems.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title={`No ${activeStatus === "All" ? "" : `${activeStatus.toLowerCase()} `}records in this scope`}
              description="Subjects appear here once workload flags are evaluated for the current scope."
            />
          ) : (
            <div className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Subject</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Credits</TableHead>
                    <TableHead>Teaching Hours</TableHead>
                    <TableHead>Students</TableHead>
                    <TableHead>Trend</TableHead>
                    <TableHead>Reason</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleItems.map((item) => (
                    <TableRow
                      key={`${item.subject_id}-${item.semester_no}-${item.academic_year}-${item.status}`}
                      className="cursor-pointer align-top"
                      onClick={() => handleRowClick(item)}
                    >
                      <TableCell>
                        <p className="font-mono text-xs text-muted-foreground">
                          {item.subject_code} · Sem {item.semester_no} · {item.academic_year}
                        </p>
                        <p className="max-w-40 truncate text-sm font-medium">{item.subject_name}</p>
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
                      </TableCell>
                      <TableCell className="tabular-nums">{item.credits}</TableCell>
                      <TableCell className="whitespace-nowrap tabular-nums">
                        {item.teaching_hours !== null ? `${item.teaching_hours}h` : "—"}
                      </TableCell>
                      <TableCell className="tabular-nums">{item.students}</TableCell>
                      <TableCell>
                        <GovernanceDelta
                          delta={item.delta}
                          previousDisplay={item.previous_display}
                          previousReason={item.previous_reason}
                        />
                      </TableCell>
                      <TableCell>
                        <p className="max-w-64 text-xs text-muted-foreground">{item.reason}</p>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          {capped && (
            <p className="text-xs text-muted-foreground">
              Showing the first {MAX_ROWS} rows — open the student table below for the full list.
            </p>
          )}
        </div>
      )}
    </section>
  )
}
