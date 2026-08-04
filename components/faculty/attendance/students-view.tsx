"use client"

import { useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  CheckSquare,
  Download,
  Search,
  Square,
  Users,
} from "lucide-react"

import { exportAttendanceCsvAction } from "@/app/faculty/attendance/actions"
import { StudentDrawer } from "@/components/faculty/students/student-drawer"
import { EmptyState } from "@/components/shared/state/empty-state"
import { ErrorState } from "@/components/shared/state/error-state"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type {
  AttendanceFilters,
  AttendanceStudentsResponse,
  AttendanceSummaryParams,
} from "@/lib/faculty-api"
import type { SectionResult } from "@/lib/section-result"
import { cn } from "@/lib/utils"

const selectClassName =
  "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"

const SORTABLE: Record<string, { label: string }> = {
  enrollment_no: { label: "Enrollment No" },
  name: { label: "Student Name" },
  semester: { label: "Sem" },
  subject: { label: "Subject" },
  attendance: { label: "Attendance" },
}

function attendanceClass(attendance: number | null): string {
  if (attendance === null) return "text-muted-foreground"
  if (attendance < 60) return "font-medium text-destructive"
  if (attendance < 75) return "font-medium text-chart-3"
  return "tabular-nums"
}

function defaulterBadge(status: string) {
  if (status === "Defaulter") {
    return (
      <span className="inline-flex items-center rounded-full bg-destructive/10 px-2.5 py-0.5 text-xs font-medium text-destructive">
        {status}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
      {status}
    </span>
  )
}

function downloadCsv(text: string, filename: string) {
  const blob = new Blob([`\ufeff${text}`], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function scopeStamp(parts: Array<string | null | undefined>): string {
  const clean = parts.filter((p): p is string => Boolean(p)).join("_") || "all"
  return clean.replace(/[^a-z0-9_]/gi, "")
}

export function StudentsView({
  data,
  filterOptions,
  filters,
}: {
  data: SectionResult<AttendanceStudentsResponse>
  filterOptions: AttendanceFilters
  filters: AttendanceSummaryParams
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const currentSearch = searchParams.get("search") || ""
  const [searchValue, setSearchValue] = useState(currentSearch)
  const [prevSearch, setPrevSearch] = useState(currentSearch)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [exporting, setExporting] = useState(false)
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null)

  if (currentSearch !== prevSearch) {
    setPrevSearch(currentSearch)
    setSearchValue(currentSearch)
    setSelected(new Set())
  }

  const handleFilterChange = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    if (key !== "page") {
      params.set("page", "1")
    }
    router.push(`${pathname}?${params.toString()}#students`)
  }

  const handleSort = (key: string) => {
    const currentSort = searchParams.get("sort") || "name"
    const currentOrder = searchParams.get("order") || "asc"
    const params = new URLSearchParams(searchParams.toString())
    if (currentSort === key) {
      params.set("order", currentOrder === "asc" ? "desc" : "asc")
    } else {
      params.set("sort", key)
      params.set("order", "asc")
    }
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}#students`)
  }

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const toggleSelectAll = () => {
    const rows = data.data?.rows ?? []
    setSelected((prev) => {
      const next = new Set(prev)
      const allSelected = rows.length > 0 && rows.every((r) => next.has(r.enrollment_record_id))
      if (allSelected) {
        rows.forEach((r) => next.delete(r.enrollment_record_id))
      } else {
        rows.forEach((r) => next.add(r.enrollment_record_id))
      }
      return next
    })
  }

  const handleExport = async (ids: string[]) => {
    setExporting(true)
    try {
      const scope = scopeStamp([
        filters.academic_year,
        filters.semester !== null && filters.semester !== undefined
          ? `sem${filters.semester}`
          : null,
        filters.subject_id,
      ])
      const res = await exportAttendanceCsvAction({
        semester: filters.semester,
        academic_year: filters.academic_year,
        subject_id: filters.subject_id,
        search: currentSearch || null,
        student_ids: ids.length ? ids : undefined,
      })
      if (res.ok) {
        downloadCsv(res.data.data, `faculty_attendance_${scope}_${Date.now()}.csv`)
      } else {
        alert(res.error.message)
      }
    } finally {
      setExporting(false)
    }
  }

  if (data.error) {
    return (
      <section id="students" className="flex scroll-mt-6 flex-col gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Students</h2>
          <p className="text-sm text-muted-foreground">
            Every enrollment in the current scope, with pagination, sorting, search, and export.
          </p>
        </div>
        <ErrorState title="Failed to load students" description={data.error} />
      </section>
    )
  }

  const students = data.data
  const rows = students?.rows ?? []
  const pagination = students?.pagination
  const sort = searchParams.get("sort") || "name"
  const order = searchParams.get("order") || "asc"
  const attendanceRange = searchParams.get("attendance_range") || ""
  const attendanceStatus = searchParams.get("attendance_status") || ""
  const defaulterStatus = searchParams.get("defaulter_status") || ""
  const studentStatus = searchParams.get("student_status") || ""
  const rowsOnPage = rows.length
  const allSelected = rowsOnPage > 0 && rows.every((r) => selected.has(r.enrollment_record_id))

  return (
    <section id="students" className="flex scroll-mt-6 flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Students</h2>
          <p className="text-sm text-muted-foreground">
            Enrollments in the current scope. Click a row for the student overview.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 print:hidden">
          {selected.size > 0 && (
            <Button
              variant="outline"
              size="sm"
              disabled={exporting}
              onClick={() => handleExport([...selected])}
            >
              <Download className="size-3.5" />
              Export selected ({selected.size})
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            disabled={exporting || (rows.length === 0 && selected.size === 0)}
            onClick={() => handleExport([])}
          >
            <Download className="size-3.5" />
            Export view
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 print:hidden">
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            placeholder="Search by name or enrollment no..."
            className="h-10 w-full bg-background pl-9"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleFilterChange("search", searchValue)
              }
            }}
          />
        </div>
        <select
          className={selectClassName}
          value={attendanceRange}
          onChange={(e) => handleFilterChange("attendance_range", e.target.value)}
          aria-label="Attendance range"
        >
          <option value="">All attendance ranges</option>
          {(filterOptions.attendance_ranges || []).map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <select
          className={selectClassName}
          value={attendanceStatus}
          onChange={(e) => handleFilterChange("attendance_status", e.target.value)}
          aria-label="Attendance status"
        >
          <option value="">All attendance statuses</option>
          {(filterOptions.attendance_statuses || []).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          className={selectClassName}
          value={defaulterStatus}
          onChange={(e) => handleFilterChange("defaulter_status", e.target.value)}
          aria-label="Defaulter status"
        >
          <option value="">All defaulter statuses</option>
          {(filterOptions.defaulter_statuses || []).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          className={selectClassName}
          value={studentStatus}
          onChange={(e) => handleFilterChange("student_status", e.target.value)}
          aria-label="Student status"
        >
          <option value="">All student statuses</option>
          {(filterOptions.student_statuses || []).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10 print:break-inside-avoid">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <button
                  type="button"
                  onClick={toggleSelectAll}
                  className="flex items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
                  aria-label={allSelected ? "Deselect all on page" : "Select all on page"}
                >
                  {allSelected ? (
                    <CheckSquare className="size-4" />
                  ) : (
                    <Square className="size-4" />
                  )}
                </button>
              </TableHead>
              {Object.entries(SORTABLE).map(([key, col]) => {
                const isActive = sort === key
                const Icon = isActive ? (order === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown
                return (
                  <TableHead key={key}>
                    <button
                      type="button"
                      onClick={() => handleSort(key)}
                      className="inline-flex items-center gap-1 transition-colors hover:text-foreground"
                    >
                      {col.label}
                      <Icon className="size-3.5 opacity-60" />
                    </button>
                  </TableHead>
                )
              })}
              <TableHead>Classes</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Defaulter</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={10} className="h-40">
                  <EmptyState
                    icon={Users}
                    title="No students found"
                    description="No enrollments match the current filters. Try clearing the search or changing the scope."
                  />
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow
                  key={row.enrollment_record_id}
                  className="cursor-pointer"
                  onClick={() => setSelectedStudentId(row.student_id)}
                >
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      onClick={() => toggleSelect(row.enrollment_record_id)}
                      className="flex items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
                      aria-label={selected.has(row.enrollment_record_id) ? "Deselect" : "Select"}
                    >
                      {selected.has(row.enrollment_record_id) ? (
                        <CheckSquare className="size-4" />
                      ) : (
                        <Square className="size-4" />
                      )}
                    </button>
                  </TableCell>
                  <TableCell className="font-medium text-muted-foreground">
                    {row.enrollment_no}
                  </TableCell>
                  <TableCell className="font-medium">
                    {row.first_name} {row.last_name}
                  </TableCell>
                  <TableCell>{row.semester_no}</TableCell>
                  <TableCell>
                    <span className="inline-flex rounded-md bg-secondary px-2 py-1 text-xs font-medium text-secondary-foreground">
                      {row.subject_code}
                    </span>
                  </TableCell>
                  <TableCell className={attendanceClass(row.attendance_percentage)}>
                    {row.attendance_percentage !== null
                      ? `${row.attendance_percentage.toFixed(1)}%`
                      : "—"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums text-muted-foreground">
                    {row.attended_classes ?? "—"} / {row.total_classes ?? "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col items-start gap-1">
                      {row.attendance_status && (
                        <span className="text-xs text-muted-foreground">{row.attendance_status}</span>
                      )}
                      {row.eligibility_status === "Not Eligible" && (
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full bg-destructive/10 px-2.5 py-0.5 text-xs font-medium text-destructive",
                          )}
                        >
                          Not Eligible
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>{defaulterBadge(row.defaulter_status)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {pagination && pagination.total_pages > 1 && (
        <div className="flex items-center justify-between px-2 pt-2">
          <p className="text-sm font-medium text-muted-foreground">
            Page {pagination.page} of {pagination.total_pages} · {pagination.total} rows
          </p>
          <div className="flex items-center gap-1 rounded-md border p-1 shadow-sm">
            <button
              className="flex h-8 items-center justify-center rounded px-3 text-sm font-medium transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50"
              disabled={pagination.page <= 1}
              onClick={() => handleFilterChange("page", (pagination.page - 1).toString())}
            >
              Previous
            </button>
            <div className="h-4 w-px bg-border" />
            <button
              className="flex h-8 items-center justify-center rounded px-3 text-sm font-medium transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50"
              disabled={pagination.page >= pagination.total_pages}
              onClick={() => handleFilterChange("page", (pagination.page + 1).toString())}
            >
              Next
            </button>
          </div>
        </div>
      )}

      <StudentDrawer studentId={selectedStudentId} onClose={() => setSelectedStudentId(null)} />
    </section>
  )
}
