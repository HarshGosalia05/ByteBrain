"use client"

import { useState } from "react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { StatCard } from "@/components/shared/data/stat-card"
import { BookOpen, Users, Calendar, Hash, FilterX, Filter, Search } from "lucide-react"
import { CURRENT_ACADEMIC_YEAR } from "@/lib/config"
import type { FacultyClassesResponse } from "@/lib/faculty-api"
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

export function ClassesTab({ data }: { data: FacultyClassesResponse }) {
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

  const handleResetFilters = () => {
    const params = new URLSearchParams(searchParams.toString())
    params.delete("search")
    params.delete("semester")
    params.set("academic_year", CURRENT_ACADEMIC_YEAR)
    params.delete("subject_id")
    params.delete("attendance_range")
    params.delete("sgpa_range")
    params.delete("grade")
    params.delete("result_status")
    params.delete("student_status")
    params.set("page", "1")
    setSearchValue("")
    router.push(`${pathname}?${params.toString()}`)
  }

  const activeFiltersCount = 
    (searchParams.get("search") ? 1 : 0) +
    (searchParams.get("semester") ? 1 : 0) +
    (searchParams.get("academic_year") ? 1 : 0) +
    (searchParams.get("subject_id") ? 1 : 0) +
    (searchParams.get("attendance_range") ? 1 : 0) +
    (searchParams.get("sgpa_range") ? 1 : 0) +
    (searchParams.get("grade") ? 1 : 0) +
    (searchParams.get("result_status") ? 1 : 0) +
    (searchParams.get("student_status") ? 1 : 0)

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <StatCard
          label="Total Classes"
          value={data.summary.total_classes.toString()}
          icon={Hash}
        />
        <StatCard
          label="Total Students"
          value={data.summary.total_students.toString()}
          icon={Users}
        />
        <StatCard
          label="Total Subjects"
          value={data.summary.total_subjects.toString()}
          icon={BookOpen}
        />
        <StatCard
          label="Current Semester"
          value={data.summary.current_semester?.toString() || "-"}
          icon={Calendar}
        />
        <StatCard
          label="Academic Year"
          value={data.summary.current_academic_year || "-"}
          icon={Calendar}
        />
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Search by name or ID..."
              className="w-full bg-background pl-9 h-10"
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
              value={searchParams.get("academic_year") || CURRENT_ACADEMIC_YEAR}
              onChange={(e) => handleFilterChange("academic_year", e.target.value)}
            >
              <option value="">All Years</option>
              {(data.filters.academic_years || []).map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"
              value={searchParams.get("semester") || ""}
              onChange={(e) => handleFilterChange("semester", e.target.value)}
            >
              <option value="">All Semesters</option>
              {(data.filters.semesters || []).map((s) => (
                <option key={s} value={s.toString()}>Semester {s}</option>
              ))}
            </select>
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:max-w-[200px]"
              value={searchParams.get("subject_id") || ""}
              onChange={(e) => handleFilterChange("subject_id", e.target.value)}
            >
              <option value="">All Subjects</option>
              {(data.filters.subjects || []).map((sub) => (
                <option key={sub.subject_id} value={sub.subject_id}>{sub.subject_code} - {sub.subject_name}</option>
              ))}
            </select>
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"
              value={searchParams.get("attendance_range") || ""}
              onChange={(e) => handleFilterChange("attendance_range", e.target.value)}
            >
              <option value="">Attendance</option>
              {(data.filters.attendance_ranges || []).map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"
              value={searchParams.get("sgpa_range") || ""}
              onChange={(e) => handleFilterChange("sgpa_range", e.target.value)}
            >
              <option value="">SGPA</option>
              {(data.filters.sgpa_ranges || []).map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"
              value={searchParams.get("grade") || ""}
              onChange={(e) => handleFilterChange("grade", e.target.value)}
            >
              <option value="">Grade</option>
              {(data.filters.grades || []).map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"
              value={searchParams.get("result_status") || ""}
              onChange={(e) => handleFilterChange("result_status", e.target.value)}
            >
              <option value="">Result</option>
              {(data.filters.result_statuses || []).map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"
              value={searchParams.get("student_status") || ""}
              onChange={(e) => handleFilterChange("student_status", e.target.value)}
            >
              <option value="">Status</option>
              {(data.filters.enrollment_statuses || []).map((r) => (
                <option key={r} value={r}>{r}</option>
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
              <TableHead>Student Name</TableHead>
              <TableHead>Sem</TableHead>
              <TableHead>Subject</TableHead>
              <TableHead>Attendance</TableHead>
              <TableHead>Performance</TableHead>
              <TableHead>Latest SGPA</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="h-32 text-center text-muted-foreground">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <Users className="size-8 opacity-20" />
                    <p>No students found matching your filters.</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              data.rows.map((row) => (
                <TableRow 
                  key={row.enrollment_record_id}
                  className="cursor-pointer"
                  onClick={() => setSelectedStudentId(row.student_id)}
                >
                  <TableCell className="font-medium text-muted-foreground">{row.enrollment_no}</TableCell>
                  <TableCell className="font-semibold">{row.first_name} {row.last_name}</TableCell>
                  <TableCell>{row.semester_no}</TableCell>
                  <TableCell>
                    <span className="inline-flex rounded-md bg-secondary px-2 py-1 text-xs font-medium text-secondary-foreground">
                      {row.subject_code}
                    </span>
                  </TableCell>
                  <TableCell>
                    {row.attendance_percentage !== null 
                      ? <span className={row.attendance_percentage < 75 ? "text-destructive font-medium" : ""}>{row.attendance_percentage.toFixed(1)}%</span>
                      : "-"}
                  </TableCell>
                  <TableCell>
                    {row.total_marks !== null ? (
                      <span className="font-medium">
                        {row.total_marks} <span className="text-muted-foreground font-normal text-xs ml-1">({row.grade || "-"})</span>
                      </span>
                    ) : "-"}
                  </TableCell>
                  <TableCell>{row.latest_sgpa?.toFixed(2) || "-"}</TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      row.enrollment_status === 'Active' ? 'bg-chart-2/10 text-chart-2' : 'bg-muted text-muted-foreground'
                    }`}>
                      {row.enrollment_status}
                    </span>
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
