import {
  getFacultyPerformanceStudents,
  type PerformanceSummaryParams,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { StudentsView } from "./students-view"

export type StudentsSectionProps = {
  filters: PerformanceSummaryParams
  search?: string
  gapStatus?: string
  page: number
  sort?: string
  order?: "asc" | "desc"
}

export async function StudentsSection({
  filters,
  search,
  gapStatus,
  page,
  sort,
  order,
}: StudentsSectionProps) {
  const result = await getFacultyPerformanceStudents({
    semester: filters.semester,
    academic_year: filters.academic_year,
    subject_id: filters.subject_id,
    page: page || 1,
    page_size: 10,
    search: search || null,
    gap_status: gapStatus || null,
    sort: sort || "name",
    order: order || "asc",
  })

  return <StudentsView data={toSectionResult(result)} filters={filters} />
}
