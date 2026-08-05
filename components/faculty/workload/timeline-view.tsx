"use client"

import { ArrowDown, ArrowUp, Minus, TrendingUp } from "lucide-react"

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
import type { WorkloadTimeline, WorkloadTimelineItem } from "@/lib/faculty-api"
import type { SectionResult } from "@/lib/section-result"
import { cn } from "@/lib/utils"

function Delta({
  item,
  previous,
}: {
  item: WorkloadTimelineItem
  previous?: WorkloadTimelineItem
}) {
  if (!previous) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Minus className="size-3.5" />
        First term
      </span>
    )
  }
  const delta = item.delta_hours
  if (delta === null) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Minus className="size-3.5" />
        No prior data
      </span>
    )
  }
  const up = delta > 0
  return (
    <div className="flex flex-col gap-0.5">
      <span
        className={cn(
          "inline-flex items-center gap-1 text-xs font-medium tabular-nums",
          delta === 0 ? "text-muted-foreground" : "text-foreground",
        )}
      >
        {up ? <ArrowUp className="size-3.5" /> : delta === 0 ? <Minus className="size-3.5" /> : <ArrowDown className="size-3.5" />}
        {delta > 0 ? `+${delta.toFixed(1)}` : delta.toFixed(1)}
        <span className="font-normal text-muted-foreground">h vs previous</span>
      </span>
      {(item.delta_students !== null || item.delta_credits !== null) && (
        <span className="text-xs text-muted-foreground">
          {item.delta_students !== null
            ? `${item.delta_students > 0 ? "+" : ""}${item.delta_students} students`
            : ""}
          {item.delta_students !== null && item.delta_credits !== null ? " · " : ""}
          {item.delta_credits !== null
            ? `${item.delta_credits > 0 ? "+" : ""}${item.delta_credits} credits`
            : ""}
        </span>
      )}
    </div>
  )
}

export function TimelineView({ data }: { data: SectionResult<WorkloadTimeline> }) {
  const items = data.data?.items ?? []

  return (
    <section id="timeline" className="flex scroll-mt-6 flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Faculty timeline</h2>
        <p className="text-sm text-muted-foreground">
          One row per term you taught — credits, hours, and students, with term-over-term deltas.
        </p>
      </div>

      {data.error ? (
        <ErrorState title="Failed to load timeline" description={data.error} />
      ) : items.length <= 1 ? (
        <div className="rounded-xl bg-card p-6 ring-1 ring-foreground/10">
          <EmptyState
            icon={TrendingUp}
            title="First term teaching"
            description="A term-over-term timeline will appear once you have taught for more than one term."
          />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Term</TableHead>
                <TableHead>Subjects</TableHead>
                <TableHead>Credits</TableHead>
                <TableHead>Students</TableHead>
                <TableHead>Weekly Hours</TableHead>
                <TableHead>Classes</TableHead>
                <TableHead>Delta</TableHead>
                <TableHead>Note</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item, index) => (
                <TableRow
                  key={`${item.semester_no}-${item.academic_year}`}
                  className={cn(
                    "align-top",
                    item.projected && "bg-primary/5",
                  )}
                >
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{item.label}</span>
                      {item.projected && <Badge variant="warning">Projected</Badge>}
                    </div>
                  </TableCell>
                  <TableCell className="tabular-nums">{item.subjects}</TableCell>
                  <TableCell className="tabular-nums">
                    {item.credits !== null ? item.credits : "—"}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {item.students !== null ? item.students : "—"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {item.weekly_hours.toFixed(1)}h
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {item.classes !== null ? item.classes : "—"}
                  </TableCell>
                  <TableCell>
                    <Delta item={item} previous={index > 0 ? items[index - 1] : undefined} />
                  </TableCell>
                  <TableCell>
                    {item.source_reason ? (
                      <p className="max-w-64 text-xs text-muted-foreground">{item.source_reason}</p>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  )
}
