"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { LayoutGrid, ChevronLeft, ChevronRight } from "lucide-react"

import { HeatmapGrid } from "@/components/shared/charts/heatmap-grid"
import { ChartCard } from "@/components/shared/data/chart-card"
import { scopeStamp } from "@/lib/csv"
import type {
  AttendanceHeatmapCell,
  AttendanceHeatmapPage,
  AttendanceSummaryParams,
  AttendanceThresholds,
} from "@/lib/faculty-api"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

type HeatmapGridPaginationProps = {
  initialData: AttendanceHeatmapPage
  filters: AttendanceSummaryParams
  thresholds: AttendanceThresholds
}

const PAGE_SIZES = [10, 20, 50] as const

export function HeatmapGridPagination({
  initialData,
  filters,
  thresholds,
}: HeatmapGridPaginationProps) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState<number>(initialData.page_size)
  const [data, setData] = useState<AttendanceHeatmapPage>(initialData)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const filtersKey = useMemo(
    () =>
      JSON.stringify({
        semester: filters.semester ?? null,
        academic_year: filters.academic_year ?? null,
        subject_id: filters.subject_id ?? null,
      }),
    [filters.semester, filters.academic_year, filters.subject_id],
  )

  useEffect(() => {
    setPage(1)
  }, [filtersKey])

  useEffect(() => {
    if (page === 1 && pageSize === initialData.page_size) {
      setData(initialData)
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)

    const params = new URLSearchParams()
    if (filters.semester !== null && filters.semester !== undefined) {
      params.set("semester", String(filters.semester))
    }
    if (filters.academic_year) params.set("academic_year", filters.academic_year)
    if (filters.subject_id) params.set("subject_id", filters.subject_id)
    params.set("page", String(page))
    params.set("page_size", String(pageSize))

    fetch(`/api/faculty/attendance/heatmap?${params.toString()}`, {
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => null)
          throw new Error(body?.error?.message ?? `HTTP ${res.status}`)
        }
        return res.json()
      })
      .then((result) => {
        if (controller.signal.aborted) return
        if (result.ok) {
          setData(result.data)
        } else {
          setError(result.error?.message ?? "Failed to load heatmap")
        }
        setLoading(false)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : "Failed to load heatmap")
        setLoading(false)
      })

    return () => controller.abort()
  }, [filters, page, pageSize, filtersKey, initialData])

  const heatmapCells: AttendanceHeatmapCell[] = data?.cells ?? []
  const totalStudents = data?.total_students ?? 0
  const totalPages = Math.max(1, Math.ceil(totalStudents / pageSize))

  const scope = scopeStamp([
    filters.academic_year,
    filters.semester ? `sem${filters.semester}` : null,
    filters.subject_id,
  ])

  const handlePageSizeChange = useCallback((value: string | null) => {
    if (!value) return
    const newSize = Number(value)
    setPageSize(newSize)
    setPage(1)
  }, [])

  const handleCellClick = useCallback(
    (cell: { subject_id: string; first_name: string; last_name: string }) => {
      const params = new URLSearchParams()
      if (filters.semester !== null && filters.semester !== undefined) {
        params.set("semester", String(filters.semester))
      }
      if (filters.academic_year) params.set("academic_year", filters.academic_year)
      params.set("subject_id", cell.subject_id)
      params.set("search", `${cell.first_name} ${cell.last_name}`.trim())
      params.set("page", "1")
      window.location.href = `/faculty/attendance?${params.toString()}#students`
    },
    [filters],
  )

  const status = error ? "error" : loading ? "loading" : heatmapCells.length ? "ready" : "empty"

  const from = totalStudents === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, totalStudents)

  return (
    <section id="attendance-heatmap" className="flex scroll-mt-6 flex-col gap-5">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Attendance heatmap</h2>
        <p className="text-sm text-muted-foreground">
          Student × subject attendance % — paginated for performance.
        </p>
      </div>

      <ChartCard
        title="Attendance heatmap"
        subtitle="Student × subject attendance %"
        status={status}
        errorDescription={error ?? undefined}
        emptyIcon={LayoutGrid}
        emptyTitle="No heatmap data"
        emptyDescription="Cells will appear here once attendance is recorded for this scope."
        exportFileName={`faculty_attendance_${scope}_heatmap.csv`}
        exportColumns={[
          { key: "student_id", label: "Student ID" },
          { key: "first_name", label: "First Name" },
          { key: "last_name", label: "Last Name" },
          { key: "subject_code", label: "Subject" },
          { key: "attendance_percentage", label: "Attendance %" },
        ]}
        exportRows={heatmapCells.map((c) => ({
          ...c,
          attendance_percentage:
            c.attendance_percentage === null ? null : Number(c.attendance_percentage.toFixed(1)),
        }))}
        className="lg:col-span-2 xl:col-span-3"
      >
        <HeatmapGrid
          cells={heatmapCells}
          critical={thresholds.critical}
          healthy={thresholds.compliance}
          onCellClick={handleCellClick}
        />
      </ChartCard>

      {totalStudents > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/50 bg-card px-4 py-3 text-sm">
          <div className="flex items-center gap-3">
            <span className="text-muted-foreground">
              Showing <span className="font-medium text-foreground">{from}–{to}</span> of{" "}
              <span className="font-medium text-foreground">{totalStudents}</span> students
            </span>
            <Select value={String(pageSize)} onValueChange={handlePageSizeChange}>
              <SelectTrigger className="h-8 w-[70px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZES.map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size} / page
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>

            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let pageNum: number
              if (totalPages <= 7) {
                pageNum = i + 1
              } else if (page <= 4) {
                pageNum = i + 1
              } else if (page >= totalPages - 3) {
                pageNum = totalPages - 6 + i
              } else {
                pageNum = page - 3 + i
              }
              return (
                <Button
                  key={pageNum}
                  variant={pageNum === page ? "default" : "outline"}
                  size="sm"
                  className="h-8 w-8 p-0 text-xs"
                  onClick={() => setPage(pageNum)}
                >
                  {pageNum}
                </Button>
              )
            })}

            <Button
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </section>
  )
}
