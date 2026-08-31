"use client"

import { useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Download, Filter, FilterX } from "lucide-react"

import { exportWorkloadCsvAction } from "@/app/faculty/workload/actions"
import { CURRENT_ACADEMIC_YEAR, ACADEMIC_YEAR_ALL } from "@/lib/config"
import type { WorkloadFilters } from "@/lib/faculty-api"
import { cn } from "@/lib/utils"

const selectClassName =
  "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"

type WorkloadFilterBarProps = {
  filters: WorkloadFilters
  hasPreviousTerm: boolean
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

export function WorkloadFilterBar({ filters, hasPreviousTerm }: WorkloadFilterBarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [exporting, setExporting] = useState(false)

  const handleExportSummary = async () => {
    setExporting(true)
    try {
      const rawYear = searchParams.get("academic_year")
      const exportYear = rawYear === ACADEMIC_YEAR_ALL || rawYear === CURRENT_ACADEMIC_YEAR ? null : rawYear
      const scope = [
        rawYear === ACADEMIC_YEAR_ALL ? "all" : rawYear,
        searchParams.get("semester") ? `sem${searchParams.get("semester")}` : null,
        searchParams.get("subject_id"),
      ]
        .filter(Boolean)
        .join("_") || "all"
      const res = await exportWorkloadCsvAction({
        semester: searchParams.get("semester")
          ? Number(searchParams.get("semester"))
          : null,
        academic_year: exportYear,
        subject_id: searchParams.get("subject_id"),
        report: "summary",
      })
      if (res.ok) {
        downloadCsv(res.data.data, `faculty_workload_summary_${scope}_${Date.now()}.csv`)
      } else {
        alert(res.error.message)
      }
    } finally {
      setExporting(false)
    }
  }

  const handleFilterChange = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    router.push(`${pathname}?${params.toString()}`)
  }

  const handleResetFilters = () => {
    const params = new URLSearchParams(searchParams.toString())
    params.delete("semester")
    params.set("academic_year", CURRENT_ACADEMIC_YEAR)
    params.delete("subject_id")
    params.delete("compare")
    router.push(`${pathname}?${params.toString()}`)
  }

  const semester = searchParams.get("semester") || ""
  const academicYear = searchParams.get("academic_year") ?? CURRENT_ACADEMIC_YEAR
  const subjectId = searchParams.get("subject_id") || ""
  const compareOn = searchParams.get("compare") === "true"
  const semesterSelected = Boolean(semester)
  const compareDisabled = !semesterSelected || !hasPreviousTerm

  const activeFiltersCount =
    (semester ? 1 : 0) + (academicYear !== CURRENT_ACADEMIC_YEAR ? 1 : 0) + (subjectId ? 1 : 0) + (compareOn ? 1 : 0)

  const compareHint = !semesterSelected
    ? "Select a semester to compare"
    : hasPreviousTerm
      ? undefined
      : "No previous term available"

  return (
    <div className="flex flex-col gap-4 print:hidden">
      <div className="flex flex-wrap items-center gap-3">
        <select
          className={selectClassName}
          value={academicYear}
          onChange={(e) => handleFilterChange("academic_year", e.target.value)}
          aria-label="Academic year"
        >
          <option value={ACADEMIC_YEAR_ALL}>All Years</option>
          {(filters.academic_years || []).map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
        <select
          className={selectClassName}
          value={semester}
          onChange={(e) => handleFilterChange("semester", e.target.value)}
          aria-label="Semester"
        >
          <option value="">All Semesters</option>
          {(filters.semesters || []).map((s) => (
            <option key={s} value={s.toString()}>
              Semester {s}
            </option>
          ))}
        </select>
        <select
          className={cn(selectClassName, "sm:max-w-[220px]")}
          value={subjectId}
          onChange={(e) => handleFilterChange("subject_id", e.target.value)}
          aria-label="Subject"
        >
          <option value="">All Subjects</option>
          {(filters.subjects || []).map((sub) => (
            <option key={sub.subject_id} value={sub.subject_id}>
              {sub.subject_code} - {sub.subject_name}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
            <button
              type="button"
              className={cn(
                "h-8 rounded px-2.5 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
                !compareOn
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
              disabled={compareDisabled}
              onClick={() => handleFilterChange("compare", "")}
              aria-pressed={!compareOn}
            >
              Current
            </button>
            <button
              type="button"
              className={cn(
                "h-8 rounded px-2.5 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
                compareOn
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
              disabled={compareDisabled}
              onClick={() => handleFilterChange("compare", "true")}
              aria-pressed={compareOn}
            >
              Previous
            </button>
          </div>
          {compareDisabled && compareHint && (
            <span className="text-xs text-muted-foreground">{compareHint}</span>
          )}
        </div>

        <button
          type="button"
          onClick={handleExportSummary}
          disabled={exporting}
          className="flex h-10 items-center gap-1.5 rounded-md border border-input bg-background px-3 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50"
          aria-label="Download workload summary report"
        >
          <Download className="size-3.5" />
          {exporting ? "Preparing…" : "Summary Report"}
        </button>

        {activeFiltersCount > 0 && (
          <div className="flex items-center gap-2">
            <div className="flex h-10 items-center gap-1.5 rounded-md border border-primary/20 bg-primary/5 px-3 text-sm font-medium text-primary">
              <Filter className="size-3.5" />
              {activeFiltersCount} Active
            </div>
            <button
              onClick={handleResetFilters}
              className="flex h-10 items-center gap-1.5 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <FilterX className="size-3.5" />
              Reset
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
