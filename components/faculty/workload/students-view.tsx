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

import { exportWorkloadCsvAction } from "@/app/faculty/workload/actions"
import { StudentProfileModal } from "@/components/faculty/students/student-profile-modal"
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
  WorkloadFilters,
  WorkloadStudentsResponse,
  WorkloadSummaryParams,
} from "@/lib/faculty-api"
import type { SectionResult } from "@/lib/section-result"
import { scopeStamp } from "@/lib/csv"
import { cn } from "@/lib/utils"

const selectClassName =
  "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"

const numberClassName =
  "h-10 w-20 rounded-md border border-input bg-background px-2 py-2 text-sm tabular-nums ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"

const SORTABLE: Record<string, { label: string }> = {
  enrollment_no: { label: "Enrollment No" },
  name: { label: "Student Name" },
  semester: { label: "Sem" },
  subject: { label: "Subject" },
  credits: { label: "Credits" },
  weekly_hours: { label: "Hours" },
  classes: { label: "Classes" },
  status: { label: "Status" },
}

function statusVariant(status: string) {
  switch (status) {
    case "Overloaded":
      return "bg-destructive/10 text-destructive"
    case "Balanced":
      return "bg-chart-2/15 text-chart-2"
    default:
      return "bg-chart-3/20 text-chart-3"
  }
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

function rangeNum(value: string | null): number | null {
  if (!value) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export function StudentsView({
  data,
  filterOptions,
  filters,
}: {
  data: SectionResult<WorkloadStudentsResponse>
  filterOptions: WorkloadFilters
  filters: WorkloadSummaryParams
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

  const rangeParam = (key: string) => searchParams.get(key) || ""
  const [rangeValues, setRangeValues] = useState<Record<string, string>>({
    credits_min: rangeParam("credits_min"),
    credits_max: rangeParam("credits_max"),
    hours_min: rangeParam("hours_min"),
    hours_max: rangeParam("hours_max"),
    students_min: rangeParam("students_min"),
    students_max: rangeParam("students_max"),
  })
  const [prevRange, setPrevRange] = useState(JSON.stringify(rangeValues))

  if (currentSearch !== prevSearch) {
    setPrevSearch(currentSearch)
    setSearchValue(currentSearch)
    setSelected(new Set())
  }

  const nextRange = JSON.stringify(rangeValues)
  if (nextRange !== prevRange) {
    setPrevRange(nextRange)
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

  const handleRangeApply = (key: string, value: string) => {
    setRangeValues((prev) => ({ ...prev, [key]: value }))
    handleFilterChange(key, value)
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
      const res = await exportWorkloadCsvAction({
        semester: filters.semester,
        academic_year: filters.academic_year,
        subject_id: filters.subject_id,
        subject_type: searchParams.get("subject_type"),
        credits_min: rangeNum(searchParams.get("credits_min")),
        credits_max: rangeNum(searchParams.get("credits_max")),
        hours_min: rangeNum(searchParams.get("hours_min")),
        hours_max: rangeNum(searchParams.get("hours_max")),
        students_min: rangeNum(searchParams.get("students_min")),
        students_max: rangeNum(searchParams.get("students_max")),
        workload_status: searchParams.get("workload_status"),
        search: currentSearch || null,
        student_ids: ids.length ? ids : undefined,
      })
      if (res.ok) {
        downloadCsv(res.data.data, `faculty_workload_${scope}_${Date.now()}.csv`)
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
  const subjectType = searchParams.get("subject_type") || ""
  const workloadStatus = searchParams.get("workload_status") || ""
  const rowsOnPage = rows.length
  const allSelected = rowsOnPage > 0 && rows.every((r) => selected.has(r.enrollment_record_id))

  const renderRange = (minKey: string, maxKey: string, minLabel: string, maxLabel: string) => (
    <div className="flex items-center gap-1.5">
      <Input
        className={cn(numberClassName, "h-9 w-20")}
        type="number"
        placeholder={minLabel}
        aria-label={minLabel}
        value={rangeValues[minKey] ?? ""}
        onChange={(e) => setRangeValues((prev) => ({ ...prev, [minKey]: e.target.value }))}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleRangeApply(minKey, e.currentTarget.value)
        }}
      />
      <span className="text-muted-foreground">–</span>
      <Input
        className={cn(numberClassName, "h-9 w-20")}
        type="number"
        placeholder={maxLabel}
        aria-label={maxLabel}
        value={rangeValues[maxKey] ?? ""}
        onChange={(e) => setRangeValues((prev) => ({ ...prev, [maxKey]: e.target.value }))}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleRangeApply(maxKey, e.currentTarget.value)
        }}
      />
    </div>
  )

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
          value={subjectType}
          onChange={(e) => handleFilterChange("subject_type", e.target.value)}
          aria-label="Subject type"
        >
          <option value="">All subject types</option>
          {(filterOptions.subject_types || []).map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          className={selectClassName}
          value={workloadStatus}
          onChange={(e) => handleFilterChange("workload_status", e.target.value)}
          aria-label="Workload status"
        >
          <option value="">All workload statuses</option>
          {(filterOptions.workload_statuses || []).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Credits</span>
          {renderRange("credits_min", "credits_max", "Min", "Max")}
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Hours</span>
          {renderRange("hours_min", "hours_max", "Min", "Max")}
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Students</span>
          {renderRange("students_min", "students_max", "Min", "Max")}
        </div>
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
                  {allSelected ? <CheckSquare className="size-4" /> : <Square className="size-4" />}
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
                    <div className="flex flex-col">
                      <span className="inline-flex w-fit rounded-md bg-secondary px-2 py-1 text-xs font-medium text-secondary-foreground">
                        {row.subject_code}
                      </span>
                      <span className="mt-0.5 max-w-40 truncate text-xs text-muted-foreground">
                        {row.subject_name}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="tabular-nums">{row.credits ?? "—"}</TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {row.weekly_hours !== null ? `${row.weekly_hours.toFixed(1)}h` : "—"}
                  </TableCell>
                  <TableCell className="tabular-nums">{row.classes_conducted ?? "—"}</TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                        statusVariant(row.workload_status),
                      )}
                    >
                      {row.workload_status}
                    </span>
                  </TableCell>
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

      <StudentProfileModal studentId={selectedStudentId} onClose={() => setSelectedStudentId(null)} />
    </section>
  )
}
