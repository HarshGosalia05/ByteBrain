import {
  getFacultyWorkloadStudents,
  type WorkloadFilters,
  type WorkloadSummaryParams,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { StudentsView } from "./students-view"

export type StudentsSectionProps = {
  filters: WorkloadSummaryParams
  filterOptions: WorkloadFilters
  subjectType?: string
  creditsMin?: number | null
  creditsMax?: number | null
  hoursMin?: number | null
  hoursMax?: number | null
  studentsMin?: number | null
  studentsMax?: number | null
  search?: string
  workloadStatus?: string
  page: number
  sort?: string
  order?: "asc" | "desc"
}

export async function StudentsSection({
  filters,
  filterOptions,
  subjectType,
  creditsMin,
  creditsMax,
  hoursMin,
  hoursMax,
  studentsMin,
  studentsMax,
  search,
  workloadStatus,
  page,
  sort,
  order,
}: StudentsSectionProps) {
  const result = await getFacultyWorkloadStudents({
    semester: filters.semester,
    academic_year: filters.academic_year,
    subject_id: filters.subject_id,
    subject_type: subjectType || null,
    credits_min: creditsMin ?? null,
    credits_max: creditsMax ?? null,
    hours_min: hoursMin ?? null,
    hours_max: hoursMax ?? null,
    students_min: studentsMin ?? null,
    students_max: studentsMax ?? null,
    search: search || null,
    workload_status: workloadStatus || null,
    page: page || 1,
    page_size: 10,
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
