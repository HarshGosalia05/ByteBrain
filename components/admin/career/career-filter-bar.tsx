"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Filter, FilterX, Search, X } from "lucide-react"

import type { DashboardFilterOptions } from "@/lib/admin-api"
import { getDepartmentBatches } from "@/lib/batch-utils"

const selectClassName =
  "h-9 min-w-36 rounded-md border border-input bg-background px-2.5 py-1 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"

const DEFAULT_DEPARTMENTS = [
  { department_code: 1, department_name: "Computer Science and Engineering", department_short_name: "CSE" },
  { department_code: 2, department_name: "Bachelor of Business Administration", department_short_name: "BBA" },
]

export function CareerFilterBar({
  filters,
}: {
  filters?: DashboardFilterOptions
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const searchParamValue = searchParams.get("search") || ""
  const [searchDraft, setSearchDraft] = React.useState(searchParamValue)
  const [prevSearchParam, setPrevSearchParam] = React.useState(searchParamValue)

  if (prevSearchParam !== searchParamValue) {
    setPrevSearchParam(searchParamValue)
    setSearchDraft(searchParamValue)
  }

  const applyParams = (key: string, value: string) => {
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
        const targetBatches = getDepartmentBatches(value, filters)
        const curBatch = params.get("batch") || params.get("academic_year")
        if (curBatch && !targetBatches.includes(curBatch)) {
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
    router.push(`${pathname}?${params.toString()}`)
  }

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    applyParams("search", searchDraft.trim())
  }

  const handleClearSearch = () => {
    setSearchDraft("")
    applyParams("search", "")
  }

  const handleResetFilters = () => {
    setSearchDraft("")
    router.push(`${pathname}?batch=2023`)
  }

  const currentBatch = searchParams.get("batch") || searchParams.get("academic_year") || ""
  const currentDept = searchParams.get("department_code") || ""
  const currentDomain = searchParams.get("preferred_domain") || ""
  const currentRole = searchParams.get("dream_job_role") || ""
  const currentInternship = searchParams.get("internship_status") || ""
  const currentReadiness = searchParams.get("placement_readiness_level") || ""
  const currentCareerStatus = searchParams.get("career_status") || ""
  const currentPackage = searchParams.get("target_package") || ""
  const currentSearch = searchParams.get("search") || ""

  const activeFiltersCount =
    (currentBatch ? 1 : 0) +
    (currentDept ? 1 : 0) +
    (currentDomain ? 1 : 0) +
    (currentRole ? 1 : 0) +
    (currentInternship ? 1 : 0) +
    (currentReadiness ? 1 : 0) +
    (currentCareerStatus ? 1 : 0) +
    (currentPackage ? 1 : 0) +
    (currentSearch ? 1 : 0)

  const availableBatches = getDepartmentBatches(currentDept, filters)

  const departmentsList =
    filters && Array.isArray(filters.departments) && filters.departments.length > 0
      ? filters.departments
      : DEFAULT_DEPARTMENTS

  const domainsList = filters?.preferred_domains || []
  const rolesList = filters?.dream_roles || []

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border/60 bg-card p-3.5 shadow-sm print:hidden">
      <div className="flex items-center justify-between gap-2 border-b border-border/40 pb-2.5">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <Filter className="size-3.5 text-primary" />
          <span>Placement & Career Filters</span>
        </div>

        {activeFiltersCount > 0 && (
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              {activeFiltersCount} Active Filter{activeFiltersCount === 1 ? "" : "s"}
            </span>
            <button
              onClick={handleResetFilters}
              className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              <FilterX className="size-3.5" />
              Clear Filters
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2.5">
        {/* Search Field */}
        <form
          onSubmit={handleSearchSubmit}
          className="flex h-9 min-w-56 flex-1 items-center gap-2 rounded-md border border-input bg-background px-3 ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2"
        >
          <Search className="size-3.5 shrink-0 text-muted-foreground" />
          <input
            type="text"
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            placeholder="Search student, domain, role, dept..."
            aria-label="Search students"
            className="h-7 min-w-0 flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
          />
          {searchDraft && (
            <button
              type="button"
              onClick={handleClearSearch}
              aria-label="Clear search"
              className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground"
            >
              <X className="size-3.5" />
            </button>
          )}
        </form>

        {/* Batch Filter */}
        <select
          className={selectClassName}
          value={currentBatch}
          onChange={(e) => applyParams("batch", e.target.value)}
          aria-label="Starting Batch"
        >
          <option value="all">All Starting Batches</option>
          {availableBatches.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>

        {/* Department Filter */}
        <select
          className={selectClassName}
          value={currentDept}
          onChange={(e) => applyParams("department_code", e.target.value)}
          aria-label="Department"
        >
          <option value="">All Departments</option>
          {departmentsList.map((d) => (
            <option key={d.department_code} value={String(d.department_code)}>
              {d.department_name || d.department_short_name || `Dept ${d.department_code}`}
            </option>
          ))}
        </select>

        {/* Preferred Domain Filter */}
        <select
          className={selectClassName}
          value={currentDomain}
          onChange={(e) => applyParams("preferred_domain", e.target.value)}
          aria-label="Preferred Domain"
        >
          <option value="">All Domains</option>
          {domainsList.map((domain) => (
            <option key={domain} value={domain}>
              {domain}
            </option>
          ))}
        </select>

        {/* Dream Role Filter */}
        <select
          className={selectClassName}
          value={currentRole}
          onChange={(e) => applyParams("dream_job_role", e.target.value)}
          aria-label="Dream Role"
        >
          <option value="">All Roles</option>
          {rolesList.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </select>

        {/* Internship Status Filter */}
        <select
          className={selectClassName}
          value={currentInternship}
          onChange={(e) => applyParams("internship_status", e.target.value)}
          aria-label="Internship Status"
        >
          <option value="">All Internships</option>
          <option value="Yes">Completed</option>
          <option value="No">Not Completed</option>
        </select>

        {/* Readiness Level Filter */}
        <select
          className={selectClassName}
          value={currentReadiness}
          onChange={(e) => applyParams("placement_readiness_level", e.target.value)}
          aria-label="Readiness Level"
        >
          <option value="">All Readiness Levels</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </select>

        {/* Career Status Filter */}
        <select
          className={selectClassName}
          value={currentCareerStatus}
          onChange={(e) => applyParams("career_status", e.target.value)}
          aria-label="Career Status"
        >
          <option value="">All Statuses</option>
          <option value="Ready">Ready</option>
          <option value="At Risk">At Risk</option>
        </select>

        {/* Target Package Filter */}
        <select
          className={selectClassName}
          value={currentPackage}
          onChange={(e) => applyParams("target_package", e.target.value)}
          aria-label="Target Package"
        >
          <option value="">All Target Packages</option>
          <option value="below_5">Below 5 LPA</option>
          <option value="5_7">5 – 7 LPA</option>
          <option value="7_10">7 – 10 LPA</option>
          <option value="above_10">Above 10 LPA</option>
        </select>
      </div>
    </div>
  )
}