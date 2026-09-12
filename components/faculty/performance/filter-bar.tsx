"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Filter, FilterX } from "lucide-react"

import { CURRENT_ACADEMIC_YEAR, ACADEMIC_YEAR_ALL } from "@/lib/config"
import type { PerformanceFilters } from "@/lib/faculty-api"
import { cn } from "@/lib/utils"

const selectClassName =
  "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"

type FilterBarProps = {
  filters: PerformanceFilters
}

export function PerformanceFilterBar({ filters }: FilterBarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

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
    router.push(`${pathname}?${params.toString()}`)
  }

  const semester = searchParams.get("semester") || ""
  const academicYear = searchParams.get("academic_year") ?? CURRENT_ACADEMIC_YEAR
  const subjectId = searchParams.get("subject_id") || ""

  const activeFiltersCount =
    (semester ? 1 : 0) + (academicYear !== CURRENT_ACADEMIC_YEAR ? 1 : 0) + (subjectId ? 1 : 0)

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
