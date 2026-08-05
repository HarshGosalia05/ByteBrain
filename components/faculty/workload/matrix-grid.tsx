import { cn } from "@/lib/utils"

export type WorkloadMatrixMode = "heatmap" | "balance" | "utilization" | "allocation"

export type WorkloadMatrixCellLike = {
  subject_id: string
  subject_code: string
  subject_name?: string | null
  semester_no?: number
  academic_year?: string
  metric: string
  label?: string
  value: number
  normalized: number
  band?: string | null
}

function termLabel(cell: WorkloadMatrixCellLike): string {
  return `Sem ${cell.semester_no ?? "—"} · ${cell.academic_year ?? "—"}`
}

function bandStyle(band?: string | null) {
  switch (band) {
    case "Overloaded":
    case "Critical":
      return { className: "bg-chart-5/20 text-chart-5", style: {} }
    case "Underutilized":
    case "Watch":
      return { className: "bg-chart-3/20 text-chart-3", style: {} }
    case "Excellent":
    case "Good":
    case "Balanced":
      return { className: "bg-chart-2/20 text-chart-2", style: {} }
    default:
      return null
  }
}

function cellStyle(mode: WorkloadMatrixMode, cell: WorkloadMatrixCellLike) {
  const band = bandStyle(cell.band)
  if (band) return band
  switch (mode) {
    case "heatmap": {
      const intensity = Math.min(1, Math.max(0, cell.normalized))
      return {
        className: "text-foreground",
        style: {
          backgroundColor: `var(--chart-1)`,
          opacity: 0.18 + 0.72 * intensity,
        },
      }
    }
    default: {
      const intensity = Math.min(1, Math.max(0, cell.normalized))
      return {
        className: "text-foreground",
        style: {
          backgroundColor: `var(--chart-4)`,
          opacity: 0.15 + 0.75 * intensity,
        },
      }
    }
  }
}

function cellDisplay(mode: WorkloadMatrixMode, cell: WorkloadMatrixCellLike): string {
  switch (mode) {
    case "heatmap":
      return String(Math.round(cell.value))
    case "balance":
      return cell.value.toFixed(1)
    default:
      return `${cell.value.toFixed(1)}%`
  }
}

export function WorkloadMatrixGrid({
  cells,
  mode,
  onCellClick,
}: {
  cells: WorkloadMatrixCellLike[]
  mode: WorkloadMatrixMode
  onCellClick?: (cell: WorkloadMatrixCellLike) => void
}) {
  const rows = new Map<string, WorkloadMatrixCellLike>()
  for (const cell of cells) {
    if (!rows.has(cell.subject_id)) {
      rows.set(cell.subject_id, cell)
    }
  }
  const subjectIds = [...rows.keys()]

  const columns: string[] =
    mode === "heatmap"
      ? [...new Map(cells.map((c) => [termLabel(c), c])).keys()]
      : [...new Map(cells.map((c) => [c.metric, c])).keys()]

  const cellKey = (cell: WorkloadMatrixCellLike) =>
    mode === "heatmap" ? termLabel(cell) : cell.metric

  const cellLookup = new Map<string, WorkloadMatrixCellLike>()
  for (const cell of cells) {
    cellLookup.set(`${cell.subject_id}::${cellKey(cell)}`, cell)
  }

  if (subjectIds.length === 0 || columns.length === 0) return null

  return (
    <div className="overflow-x-auto">
      <div
        className="grid min-w-max gap-1 text-xs"
        style={{ gridTemplateColumns: `minmax(150px, 1.6fr) repeat(${columns.length}, minmax(68px, 1fr))` }}
      >
        <div />
        {columns.map((col) => (
          <div
            key={col}
            className="flex h-9 items-center justify-center px-1.5 text-center font-medium text-muted-foreground"
          >
            {col}
          </div>
        ))}
        {subjectIds.map((subjectId) => {
          const subject = rows.get(subjectId)!
          return (
            <div key={subjectId} className="contents">
              <button
                type="button"
                onClick={() => onCellClick?.(subject)}
                className="flex min-w-0 items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted"
                title={`${subject.subject_code} - ${subject.subject_name ?? ""}`}
              >
                <span className="font-mono text-foreground">{subject.subject_code}</span>
                <span className="truncate text-muted-foreground">{subject.subject_name}</span>
              </button>
              {columns.map((col) => {
                const cell = cellLookup.get(`${subjectId}::${col}`)
                if (!cell) {
                  return <div key={col} className="h-7 rounded-md" />
                }
                const { className, style } = cellStyle(mode, cell)
                return (
                  <button
                    key={col}
                    type="button"
                    onClick={() => onCellClick?.(cell)}
                    className={cn(
                      "flex h-7 items-center justify-center rounded-md font-medium tabular-nums transition-opacity hover:opacity-80",
                      className,
                    )}
                    style={style}
                    title={`${cell.label ?? cell.metric}: ${cellDisplay(mode, cell)}`}
                  >
                    {cellDisplay(mode, cell)}
                  </button>
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}
