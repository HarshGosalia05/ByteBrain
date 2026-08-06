"use client"

import { useState } from "react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { StatCard } from "@/components/shared/data/stat-card"
import { Users, AlertCircle, CheckCircle, Percent, GraduationCap, Filter, FilterX, Search } from "lucide-react"
import type { FacultyMenteesResponse } from "@/lib/faculty-api"
import { StudentProfileModal } from "./student-profile-modal"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Input } from "@/components/ui/input"

export function MenteesTab({ data }: { data: FacultyMenteesResponse }) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const currentSearch = searchParams.get("search") || ""
  const [searchValue, setSearchValue] = useState(currentSearch)
  const [prevSearch, setPrevSearch] = useState(currentSearch)
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null)

  if (currentSearch !== prevSearch) {
    setPrevSearch(currentSearch)
    setSearchValue(currentSearch)
  }

  const handleFilterChange = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }

    // Only reset to page 1 if the filter being changed is NOT the page itself
    if (key !== "page") {
      params.set("page", "1")
    }

    router.push(`${pathname}?${params.toString()}`)
  }

  const handleFlaggedOnlyToggle = (checked: boolean) => {
    const params = new URLSearchParams(searchParams.toString())
    if (checked) {
      params.set("flagged_only", "true")
    } else {
      params.delete("flagged_only")
    }
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}`)
  }

  const handleResetFilters = () => {
    const params = new URLSearchParams(searchParams.toString())
    params.delete("search")
    params.delete("semester")
    params.delete("standing")
    params.delete("flagged_only")
    params.set("page", "1")
    setSearchValue("")
    router.push(`${pathname}?${params.toString()}`)
  }

  const activeFiltersCount =
    (searchParams.get("search") ? 1 : 0) +
    (searchParams.get("semester") ? 1 : 0) +
    (searchParams.get("standing") ? 1 : 0) +
    (searchParams.get("flagged_only") ? 1 : 0)

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <StatCard
          label="Total Mentees"
          value={data.summary.total_mentees.toString()}
          icon={Users}
        />
        <StatCard
          label="Needs Attention"
          value={data.summary.needs_attention.toString()}
          icon={AlertCircle}
          tone="destructive"
        />
        <StatCard
          label="Good Standing"
          value={data.summary.good_standing.toString()}
          icon={CheckCircle}
          tone="success"
        />
        <StatCard
          label="Avg Attendance"
          value={data.summary.average_attendance ? `${data.summary.average_attendance.toFixed(1)}%` : "-"}
          icon={Percent}
        />
        <StatCard
          label="Avg SGPA"
          value={data.summary.average_sgpa ? data.summary.average_sgpa.toFixed(2) : "-"}
          icon={GraduationCap}
        />
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Search mentee by name or ID..."
              className="w-full bg-background pl-9"
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleFilterChange("search", searchValue)
                }
              }}
            />
          </div>
          <div className="flex flex-1 flex-wrap gap-2 sm:flex-none">
            <select
              className="h-10 w-full sm:w-auto rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              value={searchParams.get("semester") || ""}
              onChange={(e) => handleFilterChange("semester", e.target.value)}
            >
              <option value="">All Semesters</option>
              {data.filters.semesters.map((s) => (
                <option key={s} value={s.toString()}>Semester {s}</option>
              ))}
            </select>
            <select
              className="h-10 w-full sm:w-auto rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 sm:w-[160px]"
              value={searchParams.get("standing") || ""}
              onChange={(e) => handleFilterChange("standing", e.target.value)}
            >
              <option value="">All Standings</option>
              {data.filters.standings.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <label className="flex h-10 w-full sm:w-auto cursor-pointer items-center justify-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm transition-colors hover:bg-muted/50 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
              <input
                type="checkbox"
                className="size-4 rounded border-input text-primary focus:ring-primary focus:ring-offset-0"
                checked={searchParams.get("flagged_only") === "true"}
                onChange={(e) => handleFlaggedOnlyToggle(e.target.checked)}
              />
              <span className="font-medium text-muted-foreground whitespace-nowrap">Flagged Only</span>
            </label>
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
              className="flex h-10 items-center gap-1.5 rounded-md px-3 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            >
              <FilterX className="size-3.5" />
              Reset
            </button>
          </div>
        )}
      </div>

      <div className="rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Enrollment No</TableHead>
              <TableHead>Mentee Name</TableHead>
              <TableHead>Sem</TableHead>
              <TableHead>Attendance</TableHead>
              <TableHead>SGPA</TableHead>
              <TableHead>Backlogs</TableHead>
              <TableHead>Flag</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <Users className="size-8 opacity-20" />
                    <p>No mentees found matching your filters.</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              data.rows.map((row) => (
                <TableRow
                  key={row.student_id}
                  className="cursor-pointer"
                  onClick={() => setSelectedStudentId(row.student_id)}
                >
                  <TableCell className="font-medium text-muted-foreground">{row.enrollment_no}</TableCell>
                  <TableCell className="font-semibold">{row.first_name} {row.last_name}</TableCell>
                  <TableCell>{row.semester}</TableCell>
                  <TableCell>
                    {row.attendance_percentage !== null
                      ? <span className={row.attendance_percentage < 75 ? "text-destructive font-medium" : ""}>{row.attendance_percentage.toFixed(1)}%</span>
                      : "-"}
                  </TableCell>
                  <TableCell className="font-medium">{row.latest_sgpa?.toFixed(2) || "-"}</TableCell>
                  <TableCell>
                    {row.backlogs !== null ? (
                      <span className={row.backlogs > 0 ? "text-destructive font-semibold" : ""}>
                        {row.backlogs}
                      </span>
                    ) : "-"}
                  </TableCell>
                  <TableCell>
                    {row.flagged ? (
                      <span
                        className="inline-flex cursor-help items-center rounded-full bg-destructive/10 px-2.5 py-0.5 text-xs font-semibold text-destructive transition-colors hover:bg-destructive/20"
                        title={row.flag_reasons.join(", ")}
                      >
                        Needs Attention
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-chart-2/10 px-2.5 py-0.5 text-xs font-semibold text-chart-2">
                        Good Standing
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

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

      <StudentProfileModal
        studentId={selectedStudentId}
        onClose={() => setSelectedStudentId(null)}
      />
    </div>
  )
}
