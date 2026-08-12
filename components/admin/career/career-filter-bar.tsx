"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Filter, FilterX, Search, X } from "lucide-react"

import type { DashboardFilterOptions } from "@/lib/admin-api"

const selectClassName =
  "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"

const DEFAULT_DEPARTMENTS = [
  { department_code: 1, department_name: "Computer Science and Engineering", department_short_name: "CSE" },
  { department_code: 2, department_name: "Bachelor of Business Administration", department_short_name: "BBA" },
]

export function CareerFilterBar({
  filters,
  onFilterChange,
  onReset,
}: {
  filters?: DashboardFilterOptions | { department_code?: number | null }
  onFilterChange?: (filters: { department_code?: number | null }) => void
  onReset?: () => void
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const [searchDraft, setSearchDraft] = React.useState(
    searchParams.get("search") || "",
  )

  const applyParams = (params: URLSearchParams) => {
    router.push(`${pathname}?${params.toString()}`)
  }

  const handleDepartmentChange = (value: string) => {
    const code = value ? parseInt(value, 10) || null : null
    onFilterChange?.({ department_code: code })
    applyParams(paramsWith(searchParams, "department_code", value))
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
    onReset?.()
    router.push(pathname)
  }

  const dp = searchParams.get("department_code")
  const defaultDp = filters && "department_code" in filters ? filters.department_code : 0
  const departmentCode = dp ? parseInt(dp, 10) || 0 : (defaultDp ?? 0)

  const activeFiltersCount =
    (departmentCode !== 0 ? 1 : 0) + (searchDraft ? 1 : 0)

  const departmentsList =
    filters && "departments" in filters && Array.isArray(filters.departments) && filters.departments.length > 0
      ? filters.departments
      : DEFAULT_DEPARTMENTS

  return (
    <div className="flex flex-col gap-4 print:hidden">
      <div className="flex flex-wrap items-center gap-3">
        <select
          className={selectClassName}
          value={departmentCode ? String(departmentCode) : ""}
          onChange={(e) => handleDepartmentChange(e.target.value)}
          aria-label="Department"
        >
          <option value="">All Departments</option>
          {departmentsList.map((d) => (
            <option key={d.department_code} value={String(d.department_code)}>
              {d.department_name || d.department_short_name || `Dept ${d.department_code}`}
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
            placeholder="Search students…"
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

function paramsWith(currentParams: URLSearchParams, key: string, value: string): URLSearchParams {
  const params = new URLSearchParams(currentParams.toString())
  if (value) {
    params.set(key, value)
  } else {
    params.delete(key)
  }
  return params
}