"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Filter, FilterX } from "lucide-react"

import type { DashboardFilterOptions } from "@/lib/admin-api"

const selectClassName =
  "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"

type AnalyticsFilterBarProps = {
  filters: DashboardFilterOptions
}

export function AnalyticsFilterBar({ filters }: AnalyticsFilterBarProps) {
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
    router.push(pathname)
  }

  const academicYear = searchParams.get("academic_year") || ""
  const departmentCode = searchParams.get("department_code") || ""
  const semester = searchParams.get("semester_no") || ""
  const activeFiltersCount =
    (academicYear ? 1 : 0) + (departmentCode ? 1 : 0) + (semester ? 1 : 0)

  // Get the selected department's total_semesters to limit semester options
  const selectedDept = filters.departments.find(
    (d) => d.department_code.toString() === departmentCode
  )
  const maxSemesters = selectedDept?.total_semesters || 8

  // Generate semester options based on selected department
  const semesterOptions = Array.from({ length: maxSemesters }, (_, i) => i + 1)

  return (
    <div className="flex flex-col gap-4 print:hidden">
      <div className="flex flex-wrap items-center gap-3">
        <select
          className={selectClassName}
          value={academicYear}
          onChange={(e) => handleFilterChange("academic_year", e.target.value)}
          aria-label="Academic year"
        >
          <option value="">All Years</option>
          {(filters.academic_years || []).map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
        <select
          className={selectClassName}
          value={departmentCode}
          onChange={(e) => {
            handleFilterChange("department_code", e.target.value)
            // Reset semester when department changes if current semester is invalid
            const newDept = filters.departments.find(
              (d) => d.department_code.toString() === e.target.value
            )
            if (newDept && semester) {
              const semNum = parseInt(semester, 10)
              if (semNum > newDept.total_semesters) {
                handleFilterChange("semester_no", "")
              }
            }
          }}
          aria-label="Department"
        >
          <option value="">All Departments</option>
          {(filters.departments || []).map((d) => (
            <option key={d.department_code} value={d.department_code.toString()}>
              {d.department_short_name || d.department_name}
            </option>
          ))}
        </select>
        <select
          className={selectClassName}
          value={semester}
          onChange={(e) => handleFilterChange("semester_no", e.target.value)}
          aria-label="Semester"
        >
          <option value="">All Semesters</option>
          {semesterOptions.map((s) => (
            <option key={s} value={s.toString()}>
              Semester {s}
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