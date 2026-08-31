"use client"

import { useState } from "react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import {
  BookOpen,
  CalendarCheck,
  Filter,
  FilterX,
  Gauge,
  GraduationCap,
  Search,
  Users,
} from "lucide-react"

import { StatCard } from "@/components/shared/data/stat-card"
import { SubjectCard } from "@/components/shared/data/subject-card"
import { EmptyState } from "@/components/shared/state/empty-state"
import { Input } from "@/components/ui/input"
import type { FacultySubjectsResponse } from "@/lib/faculty-api"

const SORT_OPTIONS = [
  { label: "Name (A–Z)", value: "name", order: "asc" },
  { label: "Performance", value: "performance", order: "desc" },
  { label: "Attendance", value: "attendance", order: "desc" },
  { label: "Enrollment", value: "students", order: "desc" },
] as const

function formatPercent(value: number | null): string {
  return value !== null ? `${value.toFixed(1)}%` : "—"
}

export function SubjectsView({ data }: { data: FacultySubjectsResponse }) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const currentSearch = searchParams.get("search") || ""
  const [searchValue, setSearchValue] = useState(currentSearch)
  const [prevSearch, setPrevSearch] = useState(currentSearch)

  if (currentSearch !== prevSearch) {
    setPrevSearch(currentSearch)
    setSearchValue(currentSearch)
  }

  // When the user has not explicitly restricted either dimension, they are
  // asking for ALL terms; signal this so the backend does not force the
  // current-term default view.
  const syncAllTerms = (params: URLSearchParams) => {
    const hasSem = params.get("semester")
    const hasYear = params.get("academic_year")
    if (!hasSem && !hasYear) {
      params.set("all_terms", "true")
    } else {
      params.delete("all_terms")
    }
  }

  const handleFilterChange = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    syncAllTerms(params)
    if (key !== "page") {
      params.set("page", "1")
    }
    router.push(`${pathname}?${params.toString()}`)
  }

  const handleSortChange = (value: string) => {
    const option = SORT_OPTIONS.find((o) => `${o.value}:${o.order}` === value)
    const params = new URLSearchParams(searchParams.toString())
    if (option) {
      params.set("sort", option.value)
      params.set("order", option.order)
    } else {
      params.delete("sort")
      params.delete("order")
    }
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}`)
  }

  const handleResetFilters = () => {
    const params = new URLSearchParams(searchParams.toString())
    params.delete("search")
    params.delete("semester")
    params.delete("academic_year")
    params.delete("batch")
    params.delete("all_terms")
    params.delete("sort")
    params.delete("order")
    params.set("page", "1")
    setSearchValue("")
    router.push(`${pathname}?${params.toString()}`)
  }

  const activeFiltersCount =
    (searchParams.get("search") ? 1 : 0) +
    (searchParams.get("semester") ? 1 : 0) +
    (searchParams.get("academic_year") ? 1 : 0) +
    (searchParams.get("batch") ? 1 : 0) +
    (searchParams.get("sort") || searchParams.get("order") ? 1 : 0)

  const sortValue = `${searchParams.get("sort") || "name"}:${searchParams.get("order") || "asc"}`
  const noAssignments = activeFiltersCount === 0 && data.cards.length === 0

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Total Subjects"
          value={data.summary.total_subjects.toString()}
          icon={BookOpen}
          hint={
            data.summary.current_semester !== null
              ? `Teaching in Sem ${data.summary.current_semester}`
              : undefined
          }
        />
        <StatCard
          label="Total Students"
          value={data.summary.total_students.toString()}
          icon={Users}
          tone="success"
        />
        <StatCard
          label="Avg attendance"
          value={formatPercent(data.summary.average_attendance)}
          icon={CalendarCheck}
        />
        <StatCard
          label="Avg performance"
          value={formatPercent(data.summary.average_performance)}
          icon={Gauge}
        />
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Search by subject code or name..."
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
          <div className="flex flex-wrap flex-1 gap-2">
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"
              value={data.applied.batch || ""}
              onChange={(e) => handleFilterChange("batch", e.target.value)}
            >
              <option value="">All Batches</option>
              {(data.filters.batches || []).map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"
              value={data.applied.academic_year || ""}
              onChange={(e) => handleFilterChange("academic_year", e.target.value)}
            >
              <option value="">All Years</option>
              {(data.filters.academic_years || []).map((y) => (
                <option key={y} value={y}>
                  {y === data.summary.current_academic_year ? `Current: ${y}` : y}
                </option>
              ))}
            </select>
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"
              value={data.applied.semester?.toString() || ""}
              onChange={(e) => handleFilterChange("semester", e.target.value)}
            >
              <option value="">All Semesters</option>
              {(data.filters.semesters || []).map((s) => (
                <option key={s} value={s.toString()}>
                  {s === data.summary.current_semester ? `Current: Sem ${s}` : `Semester ${s}`}
                </option>
              ))}
            </select>
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"
              value={sortValue}
              onChange={(e) => handleSortChange(e.target.value)}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={`${o.value}:${o.order}`} value={`${o.value}:${o.order}`}>
                  Sort: {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {activeFiltersCount > 0 && (
          <div className="flex items-center gap-2 self-start sm:self-auto">
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

      {data.cards.length === 0 ? (
        <EmptyState
          icon={GraduationCap}
          title={noAssignments ? "No subjects assigned yet" : "No subjects found"}
          description={
            noAssignments
              ? "Subjects you teach will appear here once teaching assignments are recorded."
              : "No subjects match the current filters. Try clearing the search or selecting a different term."
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.cards.map((card) => (
            <SubjectCard
              key={`${card.subject_id}-${card.semester_no}-${card.academic_year}`}
              card={card}
              href={`/faculty/subjects/${card.subject_id}?semester=${card.semester_no}&academic_year=${encodeURIComponent(card.academic_year)}`}
            />
          ))}
        </div>
      )}

      {data.pagination.total_pages > 1 && (
        <div className="flex items-center justify-between px-2 pt-2">
          <p className="text-sm font-medium text-muted-foreground">
            Page {data.pagination.page} of {data.pagination.total_pages}
          </p>
          <div className="flex items-center gap-1 rounded-md border p-1 shadow-sm">
            <button
              className="flex h-8 items-center justify-center rounded px-3 text-sm font-medium transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50"
              disabled={data.pagination.page <= 1}
              onClick={() => handleFilterChange("page", (data.pagination.page - 1).toString())}
            >
              Previous
            </button>
            <div className="h-4 w-px bg-border" />
            <button
              className="flex h-8 items-center justify-center rounded px-3 text-sm font-medium transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50"
              disabled={data.pagination.page >= data.pagination.total_pages}
              onClick={() => handleFilterChange("page", (data.pagination.page + 1).toString())}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
