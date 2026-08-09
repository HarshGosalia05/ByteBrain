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
import type { MarksChangeLogResponse } from "@/lib/faculty-api"

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—"
  if (typeof value === "number") return String(value)
  if (typeof value === "string" && value === "") return "—"
  return String(value)
}

const FIELD_LABELS: Record<string, string> = {
  internal_marks: "Internal Marks",
  mid_sem_marks: "Mid-sem Marks",
  end_sem_marks: "End-sem Marks",
  total_marks: "Total Marks",
  percentage: "Percentage",
  grade: "Grade",
  grade_point: "Grade Point",
  result_status: "Result",
  performance_category: "Performance Category",
  remarks: "Remarks",
}

function fieldLabel(fieldName: string): string {
  return FIELD_LABELS[fieldName] ?? fieldName
}

function isClearChange(item: MarksChangeLogResponse["items"][number]): boolean {
  return (
    item.new_value === null &&
    item.old_value !== null &&
    item.old_value !== undefined &&
    item.operation_type === "update"
  )
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString()
}

export function MarksChangeHistory({
  subjectId,
  semester,
  academicYear,
}: {
  subjectId: string
  semester: number
  academicYear: string
}) {
  const [data, setData] = React.useState<MarksChangeLogResponse | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  async function load() {
    try {
      const params = new URLSearchParams({
        semester: String(semester),
        academic_year: academicYear,
        page_size: "50",
      })
      const res = await fetch(
        `/api/faculty/subjects/${subjectId}/marks/change-log?${params.toString()}`,
        { cache: "no-store" },
      )
      const result = (await res.json()) as
        | { ok: true; data: MarksChangeLogResponse }
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
  }, [subjectId, semester, academicYear])

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
      <div className="flex flex-col gap-4">
        <EmptyState
          icon={History}
          title="No changes recorded yet"
          description="Once marks are saved, every changed field appears here with its old and new value."
        />
      </div>
    )
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {data.items.length} recent change{data.items.length === 1 ? "" : "s"} · Sem {semester} ·{" "}
          {academicYear}
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
                <TableCell className="font-medium">
                  {item.student_name ?? item.student_id}
                </TableCell>
                <TableCell className="font-mono text-xs">{fieldLabel(item.field_name)}</TableCell>
                <TableCell className="max-w-56 break-words text-muted-foreground">
                  {formatValue(item.old_value)}
                </TableCell>
                <TableCell className="max-w-56 break-words font-medium">
                  {isClearChange(item) ? "Cleared" : formatValue(item.new_value)}
                </TableCell>
                <TableCell>
                  <span
                    className={
                      item.operation_type === "update"
                        ? "text-chart-2"
                        : "text-muted-foreground"
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
