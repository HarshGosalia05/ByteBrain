"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Filter, FilterX, Search, X } from "lucide-react"

import type { DashboardFilterOptions } from "@/lib/admin-api"
import { getDepartmentBatches } from "@/lib/batch-utils"

const selectClassName =
  "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"

const DEFAULT_DEPARTMENTS = [
  { department_code: 1, department_name: "Computer Science and Engineering", department_short_name: "CSE" },
  { department_code: 2, department_name: "Bachelor of Business Administration", department_short_name: "BBA" },
]

export function HealthFilterBar({ filters }: { filters?: DashboardFilterOptions }) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const [searchDraft, setSearchDraft] = React.useState(
    searchParams.get("search") || "",
  )

  const batch =
    searchParams.get("batch") || searchParams.get("academic_year") || ""
  const departmentCodeParam = searchParams.get("department_code")
  const semesterParam = searchParams.get("semester")

  const dp = departmentCodeParam
    ? parseInt(departmentCodeParam, 10) || 0
    : 0
  const semester = semesterParam ? parseInt(semesterParam, 10) || 0 : 0

  const selectedDept = filters?.departments?.find(
    (d) => d.department_code === dp,
  )

  const departmentSemesters =
    selectedDept && "semesters" in selectedDept && Array.isArray((selectedDept as { semesters?: number[] }).semesters)
      ? (selectedDept as { semesters: number[] }).semesters
      : selectedDept && "total_semesters" in selectedDept
        ? Array.from(
            { length: Number((selectedDept as { total_semesters?: number }).total_semesters) || 0 },
            (_, i) => i + 1,
          )
        : filters?.semesters ?? []

  const availableBatches = getDepartmentBatches(
    dp || undefined,
    filters as Parameters<typeof getDepartmentBatches>[1],
  )

  const setParam = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    if (key === "batch") {
      params.delete("academic_year")
    }
    if (key === "department_code") {
      if (params.has("semester")) {
        const targetDept = filters?.departments?.find(
          (d) => d.department_code === parseInt(value, 10),
        )
        const validSemesters =
          targetDept && "semesters" in targetDept && Array.isArray((targetDept as { semesters?: number[] }).semesters)
            ? (targetDept as { semesters: number[] }).semesters
            : targetDept && "total_semesters" in targetDept
              ? Array.from(
                  { length: Number((targetDept as { total_semesters?: number }).total_semesters) || 0 },
                  (_, i) => i + 1,
                )
              : filters?.semesters ?? []
        const currentSem = parseInt(params.get("semester") || "0", 10)
        if (currentSem && !validSemesters.includes(currentSem)) {
          params.delete("semester")
        }
      }
      if (params.has("batch")) {
        const targetBatches = getDepartmentBatches(
          parseInt(value, 10) || undefined,
          filters as Parameters<typeof getDepartmentBatches>[1],
        )
        const currentBatch = params.get("batch") || ""
        if (currentBatch && !targetBatches.includes(currentBatch)) {
          params.delete("batch")
          params.delete("academic_year")
        }
      }
    }
    applyParams(params)
  }

  const applyParams = (params: URLSearchParams) => {
    router.push(`${pathname}?${params.toString()}`)
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
    router.push(`${pathname}?batch=2023`)
  }

  const activeFiltersCount =
    (batch ? 1 : 0) +
    (dp ? 1 : 0) +
    (semester ? 1 : 0) +
    (searchDraft ? 1 : 0)

  const departmentsList =
    filters && "departments" in filters && Array.isArray(filters.departments) && filters.departments.length > 0
      ? filters.departments
      : DEFAULT_DEPARTMENTS

  return (
    <div className="flex flex-col gap-4 print:hidden">
      <div className="flex flex-wrap items-center gap-3">
        <select
          className={selectClassName}
          value={batch}
          onChange={(e) => setParam("batch", e.target.value)}
          aria-label="Starting Batch"
        >
          <option value="all">All Starting Batches</option>
          {availableBatches.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>

        <select
          className={selectClassName}
          value={dp ? String(dp) : ""}
          onChange={(e) => setParam("department_code", e.target.value)}
          aria-label="Department"
        >
          <option value="">All Departments</option>
          {departmentsList.map((d) => (
            <option key={d.department_code} value={String(d.department_code)}>
              {d.department_name || d.department_short_name || `Dept ${d.department_code}`}
            </option>
          ))}
        </select>

        <select
          className={selectClassName}
          value={semester ? String(semester) : ""}
          onChange={(e) => setParam("semester", e.target.value)}
          aria-label="Semester"
        >
          <option value="">All Semesters</option>
          {departmentSemesters.map((s) => (
            <option key={s} value={String(s)}>
              Sem {s}
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
            placeholder="Search students..."
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
