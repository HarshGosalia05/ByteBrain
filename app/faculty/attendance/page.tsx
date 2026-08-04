import { Suspense } from "react"

import { requireRole } from "@/lib/session"
import {
  getFacultyAttendanceSummary,
  type AttendanceAppliedFilters,
  type AttendanceFilters,
  type AttendanceSummaryParams,
} from "@/lib/faculty-api"

import { AttendanceFilterBar } from "@/components/faculty/attendance/filter-bar"
import { AttendanceFreshnessStrip } from "@/components/faculty/attendance/freshness-strip"
import { AttendanceView } from "@/components/faculty/attendance/attendance-view"
import { ChartsSection } from "@/components/faculty/attendance/charts-section"
import { GovernanceSection } from "@/components/faculty/attendance/governance-section"
import { HighlightsSection } from "@/components/faculty/attendance/highlights-section"
import { StudentsSection } from "@/components/faculty/attendance/students-section"
import { ErrorState } from "@/components/shared/state/error-state"
import { LoadingSkeleton } from "@/components/shared/state/loading-skeleton"

function sectionFallback() {
  return (
    <div className="flex flex-col gap-4">
      <LoadingSkeleton />
    </div>
  )
}

function buildScopeLabel(
  applied: AttendanceAppliedFilters,
  filters: AttendanceFilters,
): string {
  const parts: string[] = []
  parts.push(applied.academic_year ?? "All Years")
  parts.push(applied.semester !== null ? `Sem ${applied.semester}` : "All Semesters")
  if (applied.subject_id) {
    const subject = filters.subjects.find((s) => s.subject_id === applied.subject_id)
    parts.push(subject ? subject.subject_code : applied.subject_id)
  }
  return parts.join(" · ")
}

export default async function AttendancePage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Faculty")

  const searchParams = await props.searchParams
  const rawSemester = typeof searchParams.semester === "string" ? searchParams.semester : undefined
  const semester = rawSemester ? parseInt(rawSemester, 10) || null : null
  const academic_year =
    typeof searchParams.academic_year === "string" ? searchParams.academic_year : undefined
  const subject_id =
    typeof searchParams.subject_id === "string" ? searchParams.subject_id : undefined
  const compare = searchParams.compare === "true"

  const search = typeof searchParams.search === "string" ? searchParams.search : undefined
  const attendance_range =
    typeof searchParams.attendance_range === "string" ? searchParams.attendance_range : undefined
  const attendance_status =
    typeof searchParams.attendance_status === "string" ? searchParams.attendance_status : undefined
  const defaulter_status =
    typeof searchParams.defaulter_status === "string" ? searchParams.defaulter_status : undefined
  const student_status =
    typeof searchParams.student_status === "string" ? searchParams.student_status : undefined
  const rawPage = typeof searchParams.page === "string" ? searchParams.page : "1"
  const page = Math.max(1, parseInt(rawPage, 10) || 1)
  const sort = typeof searchParams.sort === "string" ? searchParams.sort : "name"
  const orderRaw = typeof searchParams.order === "string" ? searchParams.order : "asc"
  const order: "asc" | "desc" = orderRaw === "desc" ? "desc" : "asc"

  const filters: AttendanceSummaryParams = {
    semester: semester === 0 ? null : semester,
    academic_year,
    subject_id,
    compare,
  }

  const res = await getFacultyAttendanceSummary(filters)
  if (!res.ok) {
    return <ErrorState title="Failed to load attendance data" description={res.error.message} />
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight">Attendance Analytics</h1>
        <p className="text-muted-foreground">
          Descriptive attendance analytics with configurable low-attendance flags and
          attendance-vs-performance views.
        </p>
      </div>
      <AttendanceFreshnessStrip
        fetchedAt={res.fetchedAt}
        scopeLabel={buildScopeLabel(res.data.applied, res.data.filters)}
        filters={filters}
      />
      <AttendanceFilterBar
        filters={res.data.filters}
        hasPreviousTerm={res.data.previous_term !== null}
      />
      <AttendanceView data={res.data}>
        <Suspense fallback={sectionFallback()}>
          <ChartsSection filters={filters} thresholds={res.data.thresholds} />
        </Suspense>
        <Suspense fallback={sectionFallback()}>
          <HighlightsSection filters={filters} />
        </Suspense>
        <Suspense fallback={sectionFallback()}>
          <GovernanceSection filters={filters} />
        </Suspense>
        <Suspense fallback={sectionFallback()}>
          <StudentsSection
            filters={filters}
            filterOptions={res.data.filters}
            search={search}
            attendanceRange={attendance_range}
            attendanceStatus={attendance_status}
            defaulterStatus={defaulter_status}
            studentStatus={student_status}
            page={page}
            sort={sort}
            order={order}
          />
        </Suspense>
      </AttendanceView>
    </div>
  )
}
