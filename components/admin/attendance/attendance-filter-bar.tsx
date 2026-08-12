"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Filter, FilterX, Search, X } from "lucide-react"

import type { DashboardFilterOptions } from "@/lib/admin-api"

const selectClassName =
  "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"

type AttendanceFilterBarProps = {
  filters: DashboardFilterOptions
}

export function AttendanceFilterBar({ filters }: AttendanceFilterBarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [searchDraft, setSearchDraft] = React.useState(
    searchParams.get("search") || "",
  )

  const academicYear = searchParams.get("academic_year") || ""
  const departmentCode = searchParams.get("department_code") || ""
  const semester = searchParams.get("semester") || ""
  const search = searchParams.get("search") || ""

  const applyParams = (params: URLSearchParams) => {
    router.push(`${pathname}?${params.toString()}`)
  }

  const handleFilterChange = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    applyParams(params)
  }

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const params = new URLSearchParams(searchParams.toString())
    const query = searchDraft.trim()
    if (query) {
      params.set("search", query)
    } else {
      params.delete("search")
    }
    applyParams(params)
  }

  const handleClearSearch = () => {
    setSearchDraft("")
    const params = new URLSearchParams(searchParams.toString())
    params.delete("search")
    applyParams(params)
  }

  const handleResetFilters = () => {
    setSearchDraft("")
    router.push(pathname)
  }

  const activeFiltersCount =
    (academicYear ? 1 : 0) + (departmentCode ? 1 : 0) + (semester ? 1 : 0) + (search ? 1 : 0)

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
          onChange={(e) => handleFilterChange("department_code", e.target.value)}
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

        <form
          onSubmit={handleSearchSubmit}
          className="flex min-w-56 items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2"
        >
          <Search className="size-4 shrink-0 text-muted-foreground" />
          <input
            type="text"
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            placeholder="Search subjects or students…"
            aria-label="Search subjects or students"
            className="h-7 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          {searchDraft && (
            <button
              type="button"
              onClick={handleClearSearch}
              aria-label="Clear search"
              className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          )}
        </form>

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
