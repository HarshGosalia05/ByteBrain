import { Suspense } from "react"

import { requireRole } from "@/lib/session"
import { CURRENT_ACADEMIC_YEAR, ACADEMIC_YEAR_ALL } from "@/lib/config"
import {
  getFacultyWorkloadSummary,
  type WorkloadAppliedFilters,
  type WorkloadFilters,
  type WorkloadSummaryParams,
} from "@/lib/faculty-api"

import { WorkloadFreshnessStrip } from "@/components/faculty/workload/freshness-strip"
import { WorkloadFilterBar } from "@/components/faculty/workload/filter-bar"
import { WorkloadView } from "@/components/faculty/workload/workload-view"
import { ChartsSection } from "@/components/faculty/workload/charts-section"
import { HighlightsSection } from "@/components/faculty/workload/highlights-section"
import { GovernanceSection } from "@/components/faculty/workload/governance-section"
import { BenchmarkSection } from "@/components/faculty/workload/benchmark-section"
import { TimelineSection } from "@/components/faculty/workload/timeline-section"
import { StudentsSection } from "@/components/faculty/workload/students-section"
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
  applied: WorkloadAppliedFilters,
  filters: WorkloadFilters,
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

function numParam(value: string | undefined): number | null {
  if (!value) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export default async function WorkloadPage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Faculty")

  const searchParams = await props.searchParams
  const rawSemester = typeof searchParams.semester === "string" ? searchParams.semester : undefined
  const semester = rawSemester ? parseInt(rawSemester, 10) || null : null
  const rawAcademicYear =
    typeof searchParams.academic_year === "string" ? searchParams.academic_year : undefined
  const academic_year =
    rawAcademicYear === ACADEMIC_YEAR_ALL
      ? undefined
      : rawAcademicYear ?? CURRENT_ACADEMIC_YEAR
  const subject_id =
    typeof searchParams.subject_id === "string" ? searchParams.subject_id : undefined
  const compare = searchParams.compare === "true"

  const subject_type =
    typeof searchParams.subject_type === "string" ? searchParams.subject_type : undefined
  const creditsMin = numParam(
    typeof searchParams.credits_min === "string" ? searchParams.credits_min : undefined,
  )
  const creditsMax = numParam(
    typeof searchParams.credits_max === "string" ? searchParams.credits_max : undefined,
  )
  const hoursMin = numParam(
    typeof searchParams.hours_min === "string" ? searchParams.hours_min : undefined,
  )
  const hoursMax = numParam(
    typeof searchParams.hours_max === "string" ? searchParams.hours_max : undefined,
  )
  const studentsMin = numParam(
    typeof searchParams.students_min === "string" ? searchParams.students_min : undefined,
  )
  const studentsMax = numParam(
    typeof searchParams.students_max === "string" ? searchParams.students_max : undefined,
  )
  const search = typeof searchParams.search === "string" ? searchParams.search : undefined
  const workload_status =
    typeof searchParams.workload_status === "string" ? searchParams.workload_status : undefined
  const rawPage = typeof searchParams.page === "string" ? searchParams.page : "1"
  const page = Math.max(1, parseInt(rawPage, 10) || 1)
  const sort = typeof searchParams.sort === "string" ? searchParams.sort : "name"
  const orderRaw = typeof searchParams.order === "string" ? searchParams.order : "asc"
  const order: "asc" | "desc" = orderRaw === "desc" ? "desc" : "asc"

  const filters: WorkloadSummaryParams = {
    semester: semester === 0 ? null : semester,
    academic_year,
    subject_id,
    compare,
  }

  const res = await getFacultyWorkloadSummary(filters)
  if (!res.ok) {
    return <ErrorState title="Failed to load workload data" description={res.error.message} />
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight">Teaching Workload</h1>
        <p className="text-muted-foreground">
          Descriptive teaching-load analytics with derived hours, capacity baselines, and
          rule-based governance flags.
        </p>
      </div>
      <WorkloadFreshnessStrip
        fetchedAt={res.fetchedAt}
        scopeLabel={buildScopeLabel(res.data.applied, res.data.filters)}
        filters={filters}
      />
      <WorkloadFilterBar
        filters={res.data.filters}
        hasPreviousTerm={res.data.previous_term !== null}
      />
      <WorkloadView data={res.data}>
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
          <BenchmarkSection filters={filters} />
        </Suspense>
        <Suspense fallback={sectionFallback()}>
          <TimelineSection />
        </Suspense>
        <Suspense fallback={sectionFallback()}>
          <StudentsSection
            filters={filters}
            filterOptions={res.data.filters}
            subjectType={subject_type}
            creditsMin={creditsMin}
            creditsMax={creditsMax}
            hoursMin={hoursMin}
            hoursMax={hoursMax}
            studentsMin={studentsMin}
            studentsMax={studentsMax}
            search={search}
            workloadStatus={workload_status}
            page={page}
            sort={sort}
            order={order}
          />
        </Suspense>
      </WorkloadView>
    </div>
  )
}
