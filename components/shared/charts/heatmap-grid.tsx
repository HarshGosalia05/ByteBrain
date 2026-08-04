"use client"

import { Fragment, useMemo } from "react"

import { cn } from "@/lib/utils"

export type HeatmapGridCell = {
  student_id: string
  subject_id: string
  subject_code: string
  first_name: string
  last_name: string
  attendance_percentage: number | null
}

type HeatmapGridProps = {
  cells: HeatmapGridCell[]
  critical: number
  healthy: number
  onCellClick?: (cell: HeatmapGridCell) => void
}

function cellClassName(value: number | null, critical: number, healthy: number): string {
  if (value === null) return "bg-muted/40 text-muted-foreground"
  if (value < critical) return "bg-destructive/15 text-destructive"
  if (value < healthy) return "bg-chart-3/20 text-chart-3"
  return "bg-chart-2/15 text-chart-2"
}

export function HeatmapGrid({ cells, critical, healthy, onCellClick }: HeatmapGridProps) {
  const subjects = useMemo(() => {
    const seen = new Map<string, string>()
    for (const cell of cells) {
      if (!seen.has(cell.subject_code)) seen.set(cell.subject_code, cell.subject_id)
    }
    return [...seen.entries()]
  }, [cells])

  const rows = useMemo(() => {
    const map = new Map<
      string,
      { name: string; values: Record<string, number | null> }
    >()
    for (const cell of cells) {
      const row = map.get(cell.student_id) ?? {
        name: `${cell.first_name} ${cell.last_name}`.trim(),
        values: {},
      }
      row.values[cell.subject_code] = cell.attendance_percentage
      map.set(cell.student_id, row)
    }
    return [...map.entries()].map(([studentId, row]) => ({ studentId, ...row }))
  }, [cells])

  if (subjects.length === 0 || rows.length === 0) {
    return null
  }

  const columns = `minmax(160px, 1.6fr) repeat(${subjects.length}, minmax(76px, 1fr))`

  return (
    <div className="overflow-x-auto">
      <div className="grid min-w-[640px] gap-1" style={{ gridTemplateColumns: columns }}>
        <div className="sticky left-0 z-10 rounded-md bg-card px-2 py-1.5 text-xs font-medium text-muted-foreground ring-1 ring-foreground/10">
          Student
        </div>
        {subjects.map(([code]) => (
          <div
            key={code}
            className="truncate rounded-md bg-muted/60 px-2 py-1.5 text-center text-xs font-medium text-muted-foreground"
            title={code}
          >
            {code}
          </div>
        ))}
        {rows.map((row) => (
          <Fragment key={row.studentId}>
            <div className="sticky left-0 z-10 truncate rounded-md bg-card px-2 py-1.5 text-xs font-medium text-foreground ring-1 ring-foreground/10">
              {row.name}
            </div>
            {subjects.map(([code, subjectId]) => {
              const value = row.values[code] ?? null
              const cell = cells.find(
                (c) => c.student_id === row.studentId && c.subject_id === subjectId,
              )
              const interactive = value !== null && Boolean(onCellClick)
              return (
                <button
                  key={`${row.studentId}-${subjectId}`}
                  type="button"
                  disabled={!interactive}
                  onClick={() => cell && onCellClick?.(cell)}
                  className={cn(
                    "rounded-md px-1 py-1.5 text-center text-xs tabular-nums",
                    cellClassName(value, critical, healthy),
                    interactive && "cursor-pointer transition-opacity hover:opacity-80",
                  )}
                  aria-label={`${row.name} in ${code}: ${value === null ? "no attendance record" : `${value.toFixed(1)}%`}`}
                >
                  {value === null ? "—" : `${Math.round(value)}%`}
                </button>
              )
            })}
          </Fragment>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-destructive/15 ring-1 ring-destructive/30" />
          Below {critical}%
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-chart-3/20 ring-1 ring-chart-3/40" />
          {critical}–{healthy}%
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-chart-2/15 ring-1 ring-chart-2/40" />
          ≥ {healthy}%
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-muted/40" />
          No record
        </span>
      </div>
    </div>
  )
}
