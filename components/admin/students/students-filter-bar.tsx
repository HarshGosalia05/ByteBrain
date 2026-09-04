"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ArrowDownWideNarrow, ArrowUpNarrowWide, Filter, FilterX, Search, X } from "lucide-react"

import type { DashboardFilterOptions } from "@/lib/admin-api"
import { getDepartmentBatches } from "@/lib/batch-utils"

const selectClassName =
  "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"

const RISK_BANDS = ["Low", "Moderate", "High", "Critical"]

const SORT_FIELDS = ["name", "sgpa", "percentage", "attendance", "backlogs", "risk"] as const

const SORT_LABELS: Record<string, string> = {
  name: "Name",
  sgpa: "SGPA",
  percentage: "Percentage",
  attendance: "Attendance",
  backlogs: "Backlogs",
  risk: "Risk",
}

type StudentsFilterBarProps = {
  filters: DashboardFilterOptions
}

export function StudentsFilterBar({ filters }: StudentsFilterBarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [searchDraft, setSearchDraft] = React.useState(
    searchParams.get("search") || "",
  )

  const batch = searchParams.get("batch") || searchParams.get("academic_year") || ""
  const departmentCode = searchParams.get("department_code") || ""
  const semester = searchParams.get("semester") || ""
  const risk = searchParams.get("risk") || ""
  const search = searchParams.get("search") || ""
  const sortByRaw = searchParams.get("sort_by") || ""
  const sortBy = SORT_FIELDS.includes(
    sortByRaw as (typeof SORT_FIELDS)[number],
  )
    ? sortByRaw
    : "name"
  const sortDir = searchParams.get("sort_dir") === "desc" ? "desc" : "asc"

  const selectedDept = (filters.departments || []).find(
    (d) => d.department_code.toString() === departmentCode
  )
  const availableSemesters =
    selectedDept?.semesters && selectedDept.semesters.length > 0
      ? selectedDept.semesters
      : selectedDept?.total_semesters
        ? Array.from({ length: selectedDept.total_semesters }, (_, i) => i + 1)
        : (filters.semesters || [])

  const availableBatches = getDepartmentBatches(departmentCode, filters)

  const applyParams = (params: URLSearchParams) => {
    router.push(`${pathname}?${params.toString()}`)
  }

  const setParam = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (key === "batch") {
      if (value) {
        params.set("batch", value)
        params.delete("academic_year")
      } else {
        params.delete("batch")
        params.delete("academic_year")
      }
    } else if (key === "department_code") {
      if (value) {
        params.set("department_code", value)
        const targetDept = (filters.departments || []).find(
          (d) => d.department_code.toString() === value
        )
        const targetSemesters =
          targetDept?.semesters && targetDept.semesters.length > 0
            ? targetDept.semesters
            : targetDept?.total_semesters
              ? Array.from({ length: targetDept.total_semesters }, (_, i) => i + 1)
              : (filters.semesters || [])
        const currentSem = params.get("semester")
        if (currentSem && !targetSemesters.includes(parseInt(currentSem, 10))) {
          params.delete("semester")
        }

        const targetBatches = getDepartmentBatches(value, filters)
        const currentBatch = params.get("batch") || params.get("academic_year")
        if (currentBatch && !targetBatches.includes(currentBatch)) {
          params.delete("batch")
          params.delete("academic_year")
        }
      } else {
        params.delete("department_code")
      }
    } else {
      if (value) {
        params.set(key, value)
      } else {
        params.delete(key)
      }
    }
    params.delete("page")
    applyParams(params)
  }

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setParam("search", searchDraft.trim())
  }

  const handleClearSearch = () => {
    setSearchDraft("")
    setParam("search", "")
  }

  const handleSortByChange = (value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("sort_by", value)
    params.set("sort_dir", "asc")
    params.delete("page")
    applyParams(params)
  }

  const handleSortDirToggle = () => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("sort_by", sortBy)
    params.set("sort_dir", sortDir === "asc" ? "desc" : "asc")
    params.delete("page")
    applyParams(params)
  }

  const handleResetFilters = () => {
    setSearchDraft("")
    router.push(pathname)
  }

  const activeFiltersCount =
    (batch ? 1 : 0) +
    (departmentCode ? 1 : 0) +
    (semester ? 1 : 0) +
    (risk ? 1 : 0) +
    (search ? 1 : 0)

  return (
    <div className="flex flex-col gap-4 print:hidden">
      <div className="flex flex-wrap items-center gap-3">
        <select
          className={selectClassName}
          value={batch}
          onChange={(e) => setParam("batch", e.target.value)}
          aria-label="Starting Batch"
        >
          <option value="">All Starting Batches</option>
          {availableBatches.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
        <select
          className={selectClassName}
          value={departmentCode}
          onChange={(e) => setParam("department_code", e.target.value)}
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
          onChange={(e) => setParam("semester", e.target.value)}
          aria-label="Semester"
        >
          <option value="">All Semesters</option>
          {availableSemesters.map((s) => (
            <option key={s} value={s.toString()}>
              Semester {s}
            </option>
          ))}
        </select>
        <select
          className={selectClassName}
          value={risk}
          onChange={(e) => setParam("risk", e.target.value)}
          aria-label="Risk band"
        >
          <option value="">All Risk Bands</option>
          {RISK_BANDS.map((band) => (
            <option key={band} value={band}>
              {band}
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
            placeholder="Search name, enrollment, email…"
            aria-label="Search students"
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

        <div className="flex items-center gap-2">
          <select
            className={selectClassName}
            value={sortBy}
            onChange={(e) => handleSortByChange(e.target.value)}
            aria-label="Sort by"
          >
            {SORT_FIELDS.map((field) => (
              <option key={field} value={field}>
                Sort: {SORT_LABELS[field]}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleSortDirToggle}
            aria-label={`Sort direction ${sortDir === "asc" ? "ascending" : "descending"}`}
            title={sortDir === "asc" ? "Ascending" : "Descending"}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-input bg-background text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            {sortDir === "asc" ? (
              <ArrowUpNarrowWide className="size-4" />
            ) : (
              <ArrowDownWideNarrow className="size-4" />
            )}
          </button>
        </div>

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
