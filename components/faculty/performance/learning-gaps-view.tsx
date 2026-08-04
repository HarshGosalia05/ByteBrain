"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  ArrowDown,
  ArrowUp,
  Minus,
  TriangleAlert,
} from "lucide-react"

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
import type { LearningGapItem, PerformanceLearningGaps } from "@/lib/faculty-api"
import type { SectionResult } from "@/lib/section-result"

function formatPercent(value: number | null): string {
  return value !== null ? `${value.toFixed(1)}%` : "—"
}

function statusBadge(status: LearningGapItem["status"]) {
  switch (status) {
    case "Critical":
      return <Badge variant="destructive">Critical</Badge>
    case "Watch":
      return <Badge variant="warning">Watch</Badge>
    default:
      return <Badge variant="success">Healthy</Badge>
  }
}

function DeltaArrow({ delta }: { delta: number | null }) {
  if (delta === null) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Minus className="size-3.5" />
        —
      </span>
    )
  }
  if (delta > 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-chart-2">
        <ArrowUp className="size-3.5" />
        +{delta.toFixed(1)}
      </span>
    )
  }
  if (delta < 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-destructive">
        <ArrowDown className="size-3.5" />
        {delta.toFixed(1)}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <Minus className="size-3.5" />
      0.0
    </span>
  )
}

export function LearningGapsView({
  data,
}: {
  data: SectionResult<PerformanceLearningGaps>
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const handleRowClick = (item: LearningGapItem) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("subject_id", item.subject_id)
    if (item.status !== "Healthy") {
      params.set("gap_status", "Below Baseline")
    } else {
      params.delete("gap_status")
    }
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}#students`)
  }

  if (data.error) {
    return (
      <section id="learning-gaps" className="flex scroll-mt-6 flex-col gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Learning gaps</h2>
          <p className="text-sm text-muted-foreground">
            Rule-based flags derived from configured performance, attendance, and pass-rate baselines.
          </p>
        </div>
        <ErrorState title="Failed to load learning gaps" description={data.error} />
      </section>
    )
  }

  const gaps = data.data
  const items = gaps?.items ?? []

  return (
    <section id="learning-gaps" className="flex scroll-mt-6 flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Learning gaps</h2>
          <p className="text-sm text-muted-foreground">
            Rule-based flags derived from configured baselines, not predictions.
          </p>
        </div>
        {gaps && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="destructive">{gaps.critical_count} Critical</Badge>
            <Badge variant="warning">{gaps.watch_count} Watch</Badge>
            <Badge variant="success">{gaps.healthy_count} Healthy</Badge>
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <EmptyState
          icon={TriangleAlert}
          title="No subjects in this scope"
          description="Subjects you teach will appear here once enrollments are recorded for this scope."
        />
      ) : (
        <div className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Subject</TableHead>
                <TableHead>Term</TableHead>
                <TableHead>Avg Performance</TableHead>
                <TableHead>Avg Attendance</TableHead>
                <TableHead>Pass Rate</TableHead>
                <TableHead>Trend</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow
                  key={`${item.subject_id}-${item.semester_no}-${item.academic_year}`}
                  className="cursor-pointer align-top"
                  onClick={() => handleRowClick(item)}
                >
                  <TableCell>
                    <p className="font-mono text-xs text-muted-foreground">{item.subject_code}</p>
                    <p className="font-medium">{item.subject_name}</p>
                    {item.reason && (
                      <p className="mt-1 max-w-xs text-xs text-muted-foreground">{item.reason}</p>
                    )}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    Sem {item.semester_no} · {item.academic_year}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {formatPercent(item.average_performance)}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {formatPercent(item.average_attendance)}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {formatPercent(item.pass_percentage)}
                  </TableCell>
                  <TableCell>
                    <DeltaArrow delta={item.delta} />
                  </TableCell>
                  <TableCell>{statusBadge(item.status)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  )
}
