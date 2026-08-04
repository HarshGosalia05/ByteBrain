import {
  getFacultyAttendanceStudents,
  type AttendanceFilters,
  type AttendanceSummaryParams,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { StudentsView } from "./students-view"

export type StudentsSectionProps = {
  filters: AttendanceSummaryParams
  filterOptions: AttendanceFilters
  search?: string
  attendanceRange?: string
  attendanceStatus?: string
  defaulterStatus?: string
  studentStatus?: string
  page: number
  sort?: string
  order?: "asc" | "desc"
}

export async function StudentsSection({
  filters,
  filterOptions,
  search,
  attendanceRange,
  attendanceStatus,
  defaulterStatus,
  studentStatus,
  page,
  sort,
  order,
}: StudentsSectionProps) {
  const result = await getFacultyAttendanceStudents({
    semester: filters.semester,
    academic_year: filters.academic_year,
    subject_id: filters.subject_id,
    page: page || 1,
    page_size: 10,
    search: search || null,
    attendance_range: attendanceRange || null,
    attendance_status: attendanceStatus || null,
    defaulter_status: defaulterStatus || null,
    student_status: studentStatus || null,
    sort: sort || "name",
    order: order || "asc",
  })

  return (
    <StudentsView
      data={toSectionResult(result)}
      filterOptions={filterOptions}
      filters={filters}
    />
  )
}
