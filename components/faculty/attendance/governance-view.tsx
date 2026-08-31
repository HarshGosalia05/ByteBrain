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
import type {
  AttendanceGovernance,
  AttendanceGovernanceItem,
  AttendanceHealthScore,
} from "@/lib/faculty-api"
import type { SectionResult } from "@/lib/section-result"
import { cn } from "@/lib/utils"

const MAX_ROWS_PER_BAND = 50

type GovernanceViewProps = {
  governance: SectionResult<AttendanceGovernance>
  healthScore: SectionResult<AttendanceHealthScore>
}

type Band = "Critical" | "Watch" | "Healthy" | "All"

function formatPercent(value: number | null): string {
  return value !== null ? `${value.toFixed(1)}%` : "—"
}

function healthVariant(band: string): "destructive" | "warning" | "success" | "muted" {
  switch (band) {
    case "Critical":
      return "destructive"
    case "Watch":
      return "warning"
    case "No Data":
      return "muted"
    default:
      return "success"
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

export function GovernanceView({ governance, healthScore }: GovernanceViewProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const activeBand = (searchParams.get("band") as Band) || "Critical"

  const selectBand = (band: Band) => {
    const params = new URLSearchParams(searchParams.toString())
    if (band === "All") {
      params.delete("band")
    } else {
      params.set("band", band)
    }
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}#governance`)
  }

  const handleRowClick = (item: AttendanceGovernanceItem) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("subject_id", item.subject_id)
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}#students`)
  }

  const health = healthScore.data
  const gov = governance.data
  const allItems = gov?.items ?? []
  const shownItems =
    activeBand === "All"
      ? allItems
      : allItems.filter((item) => item.band === activeBand)
  const capped = shownItems.length > MAX_ROWS_PER_BAND
  const visibleItems = shownItems.slice(0, MAX_ROWS_PER_BAND)

  return (
    <section id="governance" className="flex scroll-mt-6 flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Governance &amp; defaulter review</h2>
          <p className="text-sm text-muted-foreground">
            Rule-based attendance bands with visible reasons, not predictions.
          </p>
        </div>
        {gov && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="destructive">{gov.critical_count} Critical</Badge>
            <Badge variant="warning">{gov.watch_count} Watch</Badge>
            <Badge variant="success">{gov.healthy_count} Healthy</Badge>
          </div>
        )}
      </div>

      {healthScore.error ? (
        <ErrorState title="Failed to load attendance health" description={healthScore.error} />
      ) : health ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
            <Badge variant={healthVariant(health.scope_band)} className="capitalize">
              {health.scope_band}
            </Badge>
            <p className="text-sm text-muted-foreground">{health.scope_reason}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {health.subjects.map((s, idx) => (
              <div key={`${s.subject_id ?? "null"}-${idx}`} className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
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
                  {formatPercent(s.attendance_percentage)}
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
            <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
              {(["Critical", "Watch", "Healthy", "All"] as Band[]).map((band) => (
                <button
                  key={band}
                  type="button"
                  className={cn(
                    "h-8 rounded px-2.5 text-sm font-medium transition-colors",
                    activeBand === band
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                  onClick={() => selectBand(band)}
                  aria-pressed={activeBand === band}
                >
                  {band}
                </button>
              ))}
            </div>
          </div>

          {visibleItems.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title={`No ${activeBand === "All" ? "" : `${activeBand.toLowerCase()} `}records in this scope`}
              description="Students appear here once attendance is recorded for the current scope."
            />
          ) : (
            <div className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Student</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Attendance</TableHead>
                    <TableHead>Classes</TableHead>
                    <TableHead>Band</TableHead>
                    <TableHead>Trend</TableHead>
                    <TableHead>Reason</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleItems.map((item) => (
                    <TableRow
                      key={item.enrollment_record_id}
                      className="cursor-pointer align-top"
                      onClick={() => handleRowClick(item)}
                    >
                      <TableCell>
                        <p className="font-medium">
                          {item.first_name} {item.last_name}
                        </p>
                        <p className="font-mono text-xs text-muted-foreground">{item.enrollment_no}</p>
                      </TableCell>
                      <TableCell>
                        <p className="font-mono text-xs text-muted-foreground">{item.subject_code}</p>
                        <p className="max-w-40 truncate text-sm">{item.subject_name}</p>
                      </TableCell>
                      <TableCell className="tabular-nums">
                        <p>{formatPercent(item.attendance_percentage)}</p>
                        {item.attendance_status && (
                          <p className="text-xs text-muted-foreground">{item.attendance_status}</p>
                        )}
                      </TableCell>
                      <TableCell className="whitespace-nowrap tabular-nums text-muted-foreground">
                        {item.attended_classes ?? "—"} / {item.total_classes ?? "—"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={healthVariant(item.band)}>{item.band}</Badge>
                      </TableCell>
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
              Showing the first {MAX_ROWS_PER_BAND} rows — open the student table below for the full
              list.
            </p>
          )}
        </div>
      )}
    </section>
  )
}
