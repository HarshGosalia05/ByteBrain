"use client"

import { useState, useMemo } from "react"
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Download,
  Search,
  X,
} from "lucide-react"

import type { ShortageStudentRow } from "@/lib/admin-api"

const selectClassName =
  "h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"

const SORT_OPTIONS = [
  { key: "attendance", label: "Lowest Attendance" },
  { key: "attendance_desc", label: "Highest Attendance" },
  { key: "shortage_count", label: "Most Shortage Subjects" },
  { key: "name", label: "Student Name A–Z" },
] as const

const ATTENDANCE_RANGE_OPTIONS = [
  { value: "", label: "All Below Target" },
  { value: "<50", label: "Below 50%" },
  { value: "<60", label: "Below 60%" },
  { value: "<75", label: "Below 75%" },
]

const PAGE_SIZE = 10

function toFixed(value: number | null, digits = 2): string {
  if (value === null || value === undefined) return "—"
  return value.toFixed(digits)
}

function severityBand(attendance: number | null): "critical" | "high" | "warning" | null {
  if (attendance === null) return null
  if (attendance < 50) return "critical"
  if (attendance < 60) return "high"
  if (attendance < 75) return "warning"
  return null
}

function severityBadge(band: "critical" | "high" | "warning" | null) {
  if (band === "critical") {
    return (
      <span className="inline-flex items-center rounded-md bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
        Critical
      </span>
    )
  }
  if (band === "high") {
    return (
      <span className="inline-flex items-center rounded-md bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
        High
      </span>
    )
  }
  if (band === "warning") {
    return (
      <span className="inline-flex items-center rounded-md bg-chart-3/15 px-2 py-0.5 text-xs font-medium text-chart-3">
        Warning
      </span>
    )
  }
  return null
}

function downloadCsv(text: string, filename: string) {
  const blob = new Blob(["\ufeff" + text], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function buildCsv(flatRows: ShortageStudentRow[]): string {
  const header = "Student,Student ID,Department,Semester,Subject Code,Subject,Attendance,Target,Shortage,Eligibility"
  const lines = flatRows.map(
    (r) =>
      [
        `"${r.student_name}"`,
        r.student_id,
        `"${r.department_name}"`,
        r.semester,
        r.subject_code,
        `"${r.subject_name}"`,
        r.attendance_percentage !== null ? r.attendance_percentage.toFixed(2) : "",
        r.required_target.toFixed(2),
        r.shortage !== null ? r.shortage.toFixed(2) : "",
        r.eligibility_status ?? "",
      ].join(","),
  )
  return [header, ...lines].join("\n")
}

type GroupedStudent = {
  student_id: string
  student_name: string
  enrollment_no: number
  department_name: string
  lowest_attendance: number | null
  subjects: ShortageStudentRow[]
}

export function ShortageStudentsGrouped({
  rows,
  total,
  studentsTotal,
  requiredTarget,
}: {
  rows: ShortageStudentRow[]
  total: number
  studentsTotal: number
  requiredTarget: number
}) {
  const [search, setSearch] = useState("")
  const [departmentFilter, setDepartmentFilter] = useState("")
  const [semesterFilter, setSemesterFilter] = useState("")
  const [subjectFilter, setSubjectFilter] = useState("")
  const [attendanceRange, setAttendanceRange] = useState("")
  const [sortKey, setSortKey] = useState<string>("attendance")
  const [page, setPage] = useState(1)
  const [expandedStudents, setExpandedStudents] = useState<Set<string>>(new Set())

  const departments = useMemo(() => {
    const map = new Map<number, string>()
    for (const r of rows) {
      if (!map.has(r.department_code)) map.set(r.department_code, r.department_name)
    }
    return Array.from(map.entries())
      .sort((a, b) => a[1].localeCompare(b[1]))
      .map(([code, name]) => ({ code, name }))
  }, [rows])

  const semesters = useMemo(() => {
    const set = new Set<number>()
    for (const r of rows) set.add(r.semester)
    return Array.from(set).sort((a, b) => a - b)
  }, [rows])

  const subjects = useMemo(() => {
    const map = new Map<string, string>()
    for (const r of rows) {
      if (!map.has(r.subject_code)) map.set(r.subject_code, r.subject_name)
    }
    return Array.from(map.entries())
      .sort((a, b) => a[1].localeCompare(b[1]))
      .map(([code, name]) => ({ code, name }))
  }, [rows])

  const filtered = useMemo(() => {
    let result = rows

    if (search) {
      const q = search.toLowerCase()
      result = result.filter(
        (r) =>
          r.student_name.toLowerCase().includes(q) ||
          r.student_id.toLowerCase().includes(q) ||
          r.subject_code.toLowerCase().includes(q) ||
          r.subject_name.toLowerCase().includes(q),
      )
    }

    if (departmentFilter) {
      const deptCode = parseInt(departmentFilter, 10)
      result = result.filter((r) => r.department_code === deptCode)
    }

    if (semesterFilter) {
      const sem = parseInt(semesterFilter, 10)
      result = result.filter((r) => r.semester === sem)
    }

    if (subjectFilter) {
      result = result.filter((r) => r.subject_code === subjectFilter)
    }

    if (attendanceRange) {
      const threshold = parseFloat(attendanceRange.replace("<", ""))
      result = result.filter((r) => r.attendance_percentage !== null && r.attendance_percentage < threshold)
    }

    return result
  }, [rows, search, departmentFilter, semesterFilter, subjectFilter, attendanceRange])

  const grouped = useMemo(() => {
    const map = new Map<string, GroupedStudent>()
    for (const r of filtered) {
      let g = map.get(r.student_id)
      if (!g) {
        g = {
          student_id: r.student_id,
          student_name: r.student_name,
          enrollment_no: r.enrollment_no,
          department_name: r.department_name,
          lowest_attendance: r.attendance_percentage,
          subjects: [],
        }
        map.set(r.student_id, g)
      }
      g.subjects.push(r)
      if (r.attendance_percentage !== null) {
        if (g.lowest_attendance === null || r.attendance_percentage < g.lowest_attendance) {
          g.lowest_attendance = r.attendance_percentage
        }
      }
    }
    return Array.from(map.values())
  }, [filtered])

  const sorted = useMemo(() => {
    const arr = [...grouped]
    switch (sortKey) {
      case "attendance":
        arr.sort((a, b) => {
          if (a.lowest_attendance === null) return 1
          if (b.lowest_attendance === null) return -1
          return a.lowest_attendance - b.lowest_attendance
        })
        break
      case "attendance_desc":
        arr.sort((a, b) => {
          if (a.lowest_attendance === null) return 1
          if (b.lowest_attendance === null) return -1
          return b.lowest_attendance - a.lowest_attendance
        })
        break
      case "shortage_count":
        arr.sort((a, b) => b.subjects.length - a.subjects.length)
        break
      case "name":
        arr.sort((a, b) => a.student_name.localeCompare(b.student_name))
        break
    }
    return arr
  }, [grouped, sortKey])

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const paged = sorted.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  const toggleExpand = (studentId: string) => {
    setExpandedStudents((prev) => {
      const next = new Set(prev)
      if (next.has(studentId)) {
        next.delete(studentId)
      } else {
        next.add(studentId)
      }
      return next
    })
  }

  const handleExport = () => {
    const csv = buildCsv(filtered)
    downloadCsv(csv, `admin_shortage_students_grouped_${Date.now()}.csv`)
  }

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      setPage(1)
      setExpandedStudents(new Set())
    }
  }

  const handleFilterChange = (setter: (v: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => {
    setter(e.target.value)
    setPage(1)
    setExpandedStudents(new Set())
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Shortage Students</h2>
          <p className="text-sm text-muted-foreground">
            Students below the {toFixed(requiredTarget)}% attendance target
          </p>
        </div>
        <button
          onClick={handleExport}
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-input bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"
        >
          <Download className="size-3.5" />
          Export CSV
        </button>
      </div>

      <p className="text-sm font-medium text-muted-foreground">
        {studentsTotal} student{studentsTotal === 1 ? "" : "s"} · {total} subject shortage{total === 1 ? "" : "s"}
      </p>

      <div className="grid grid-cols-1 items-center gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-[2fr_1fr_1fr_1.2fr_1fr_1fr]">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder="Search student, ID or subject…"
            aria-label="Search students or subjects"
            className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-8 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          />
          {search && (
            <button
              type="button"
              onClick={() => { setSearch(""); setPage(1) }}
              aria-label="Clear search"
              className="absolute right-2 top-2.5 rounded p-0.5 text-muted-foreground hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          )}
        </div>

        <select
          className={selectClassName}
          value={departmentFilter}
          onChange={handleFilterChange(setDepartmentFilter)}
          aria-label="Department"
        >
          <option value="">All Departments</option>
          {departments.map((d) => (
            <option key={d.code} value={d.code.toString()}>
              {d.name}
            </option>
          ))}
        </select>

        <select
          className={selectClassName}
          value={semesterFilter}
          onChange={handleFilterChange(setSemesterFilter)}
          aria-label="Semester"
        >
          <option value="">All Semesters</option>
          {semesters.map((s) => (
            <option key={s} value={s.toString()}>
              Semester {s}
            </option>
          ))}
        </select>

        <select
          className={selectClassName}
          value={subjectFilter}
          onChange={handleFilterChange(setSubjectFilter)}
          aria-label="Subject"
        >
          <option value="">All Subjects</option>
          {subjects.map((s) => (
            <option key={s.code} value={s.code}>
              {s.name} ({s.code})
            </option>
          ))}
        </select>

        <select
          className={selectClassName}
          value={attendanceRange}
          onChange={handleFilterChange(setAttendanceRange)}
          aria-label="Attendance range"
        >
          {ATTENDANCE_RANGE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        <select
          className={selectClassName}
          value={sortKey}
          onChange={(e) => { setSortKey(e.target.value); setPage(1) }}
          aria-label="Sort by"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.key} value={opt.key}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {paged.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-8 text-center">
          <AlertTriangle className="size-8 text-muted-foreground" />
          <p className="text-sm font-medium">No shortage students</p>
          <p className="text-xs text-muted-foreground">
            No students are below the attendance target in the current selection.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-xs text-muted-foreground uppercase">
                <th className="py-3 px-4 w-10"></th>
                <th className="py-3 px-4 font-medium">Student</th>
                <th className="py-3 px-4 font-medium">Enrollment</th>
                <th className="py-3 px-4 font-medium">Department</th>
                <th className="py-3 px-4 text-right font-medium">Lowest Att.</th>
                <th className="py-3 px-4 text-right font-medium">Shortage Subjects</th>
                <th className="py-3 px-4 text-right font-medium">Severity</th>
                <th className="py-3 px-4 w-20"></th>
              </tr>
            </thead>
            <tbody>
              {paged.map((student) => {
                const isExpanded = expandedStudents.has(student.student_id)
                const band = severityBand(student.lowest_attendance)
                return [
                  <tr
                    key={student.student_id}
                    className="border-b last:border-0 transition-colors hover:bg-muted/30"
                  >
                    <td className="py-3 px-4 text-center">
                      <button
                        type="button"
                        onClick={() => toggleExpand(student.student_id)}
                        className="text-muted-foreground hover:text-foreground"
                        aria-label={isExpanded ? "Collapse" : "Expand"}
                      >
                        {isExpanded ? (
                          <ChevronUp className="size-4 mx-auto" />
                        ) : (
                          <ChevronDown className="size-4 mx-auto" />
                        )}
                      </button>
                    </td>
                    <td className="py-3 px-4">
                      <p className="font-medium">{student.student_name}</p>
                      <p className="text-xs text-muted-foreground font-mono">{student.student_id}</p>
                    </td>
                    <td className="py-3 px-4 text-xs tabular-nums">{student.enrollment_no}</td>
                    <td className="py-3 px-4 text-xs text-muted-foreground">{student.department_name}</td>
                    <td className="py-3 px-4 text-right tabular-nums font-medium">
                      <span className={band === "critical" || band === "high" ? "text-destructive" : band === "warning" ? "text-chart-3" : ""}>
                        {toFixed(student.lowest_attendance)}%
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right tabular-nums">
                      {student.subjects.length} subject{student.subjects.length !== 1 ? "s" : ""}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {severityBadge(band)}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <button
                        type="button"
                        onClick={() => toggleExpand(student.student_id)}
                        className="text-xs text-muted-foreground hover:text-foreground underline"
                      >
                        {isExpanded ? "Hide" : "Details"}
                      </button>
                    </td>
                  </tr>,
                  isExpanded && (
                    <tr key={`${student.student_id}-detail`} className="bg-muted/20">
                      <td colSpan={8} className="py-0">
                        <div className="px-4 pb-4 pt-2 space-y-3">
                          <div className="grid gap-2 sm:grid-cols-3 text-xs">
                            <div className="col-span-3 font-medium text-muted-foreground">
                              Shortage Subjects ({student.subjects.length})
                            </div>
                            {student.subjects.map((subj) => (
                              <div
                                key={student.student_id + "-" + subj.subject_code}
                                className="col-span-3 rounded-lg border p-3 bg-background"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <div className="flex-1 min-w-0">
                                    <p className="font-medium truncate">{subj.subject_name}</p>
                                    <p className="text-xs text-muted-foreground font-mono">
                                      {subj.subject_code} · Sem {subj.semester}
                                    </p>
                                  </div>
                                  <div className="flex flex-col items-end gap-1 text-right">
                                    <p className={subj.attendance_percentage !== null && subj.attendance_percentage < 60 ? "text-destructive font-medium" : "text-chart-3 font-medium"}>
                                      {toFixed(subj.attendance_percentage)}%
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                      Target: {toFixed(subj.required_target)}%
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                      Shortage: {subj.shortage !== null ? `${toFixed(subj.shortage)} pp` : "—"}
                                    </p>
                                    {subj.eligibility_status === "Not Eligible" && (
                                      <span className="inline-flex items-center rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
                                        Not Eligible
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ),
                ]
              })}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {safePage} of {totalPages}
          </p>
          <div className="flex items-center gap-1 rounded-md border p-1">
            <button
              className="flex h-8 items-center justify-center rounded px-3 text-sm font-medium transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50"
              disabled={safePage <= 1}
              onClick={() => { setPage(safePage - 1); setExpandedStudents(new Set()) }}
            >
              <ChevronLeft className="size-4" />
            </button>
            <div className="h-4 w-px bg-border" />
            <button
              className="flex h-8 items-center justify-center rounded px-3 text-sm font-medium transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50"
              disabled={safePage >= totalPages}
              onClick={() => { setPage(safePage + 1); setExpandedStudents(new Set()) }}
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
