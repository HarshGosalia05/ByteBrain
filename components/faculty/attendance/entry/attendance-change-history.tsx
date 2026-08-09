"use client"

import * as React from "react"
import { History, LoaderCircle, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
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
import type { AttendanceChangeLogResponse } from "@/lib/faculty-api"

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—"
  if (typeof value === "number") return String(value)
  if (typeof value === "string" && value === "") return "—"
  return String(value)
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString()
}

export function AttendanceChangeHistory({
  subjectId,
  semester,
  academicYear,
  lectureDate,
  slotNo,
}: {
  subjectId: string
  semester?: number
  academicYear?: string
  lectureDate?: string
  slotNo?: number
}) {
  const [data, setData] = React.useState<AttendanceChangeLogResponse | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  async function load() {
    try {
      const params = new URLSearchParams({ page_size: "50" })
      if (semester !== undefined && semester !== null && !Number.isNaN(semester))
        params.set("semester", String(semester))
      if (academicYear) params.set("academic_year", academicYear)
      if (lectureDate) params.set("lecture_date", lectureDate)
      if (slotNo !== undefined && slotNo !== null) params.set("slot_no", String(slotNo))
      const res = await fetch(
        `/api/faculty/subjects/${subjectId}/attendance/change-log?${params.toString()}`,
        { cache: "no-store" },
      )
      const result = (await res.json()) as
        | { ok: true; data: AttendanceChangeLogResponse }
        | { ok: false; error: { status: number; message: string } }
      if (!result.ok) {
        setError(result.error.message)
        return
      }
      setData(result.data)
    } catch {
      setError("Could not load the change history. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subjectId, semester, academicYear, lectureDate, slotNo])

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
        <LoaderCircle className="size-4 animate-spin" />
        Loading change history…
      </p>
    )
  }

  if (error) {
    return <ErrorState title="Failed to load change history" description={error} />
  }

  if (!data || data.items.length === 0) {
    return (
      <EmptyState
        icon={History}
        title="No changes recorded yet"
        description="Once lecture attendance is saved, every changed status appears here."
      />
    )
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {data.items.length} recent change{data.items.length === 1 ? "" : "s"}
          {lectureDate ? ` · ${lectureDate}` : ""}
          {slotNo !== undefined && slotNo !== null ? ` · slot ${slotNo}` : ""}
          {semester !== undefined ? ` · Sem ${semester}` : ""}
          {academicYear ? ` · ${academicYear}` : ""}
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setLoading(true)
            setError(null)
            void load()
          }}
        >
          <RefreshCw className="size-3.5" />
          Refresh
        </Button>
      </div>
      <div className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>When</TableHead>
              <TableHead>Lecture</TableHead>
              <TableHead>Student</TableHead>
              <TableHead>Field</TableHead>
              <TableHead>Old value</TableHead>
              <TableHead>New value</TableHead>
              <TableHead>Operation</TableHead>
              <TableHead>By</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((item) => (
              <TableRow key={item.change_id}>
                <TableCell className="whitespace-nowrap text-muted-foreground">
                  {formatWhen(item.changed_at)}
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {item.lecture_date} · slot {item.slot_no}
                </TableCell>
                <TableCell className="font-medium">
                  {item.student_name ?? item.student_id}
                </TableCell>
                <TableCell className="font-mono text-xs">{item.field_name}</TableCell>
                <TableCell className="max-w-56 break-words text-muted-foreground">
                  {formatValue(item.old_value)}
                </TableCell>
                <TableCell className="max-w-56 break-words font-medium">
                  {formatValue(item.new_value)}
                </TableCell>
                <TableCell>
                  <span
                    className={
                      item.operation_type === "update" ? "text-chart-2" : "text-muted-foreground"
                    }
                  >
                    {item.operation_type}
                  </span>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {item.changed_by ?? "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  )
}
