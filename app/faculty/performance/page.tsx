import { Suspense } from "react"

import { requireRole } from "@/lib/session"
import { CURRENT_ACADEMIC_YEAR, ACADEMIC_YEAR_ALL } from "@/lib/config"
import {
  getFacultyPerformanceSummary,
  type PerformanceAppliedFilters,
  type PerformanceFilters,
  type PerformanceSummaryParams,
} from "@/lib/faculty-api"

import { PerformanceView } from "@/components/faculty/performance/performance-view"
import { PerformanceFilterBar } from "@/components/faculty/performance/filter-bar"
import { FreshnessStrip } from "@/components/faculty/performance/freshness-strip"
import { ChartsSection } from "@/components/faculty/performance/charts-section"
import { InsightsSection } from "@/components/faculty/performance/insights-section"
import { LearningGapsSection } from "@/components/faculty/performance/learning-gaps-section"
import { StudentsSection } from "@/components/faculty/performance/students-section"
import { ErrorState } from "@/components/shared/state/error-state"
import { LoadingSkeleton } from "@/components/shared/state/loading-skeleton"

function buildScopeLabel(
  applied: PerformanceAppliedFilters,
  filters: PerformanceFilters,
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

function sectionFallback() {
  return (
    <div className="flex flex-col gap-4">
      <LoadingSkeleton />
    </div>
  )
}

export default async function PerformancePage(props: {
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
  const search = typeof searchParams.search === "string" ? searchParams.search : undefined
  const gapStatus =
    typeof searchParams.gap_status === "string" ? searchParams.gap_status : undefined
  const page = typeof searchParams.page === "string" ? parseInt(searchParams.page, 10) || 1 : 1
  const sort = typeof searchParams.sort === "string" ? searchParams.sort : undefined
  const order =
    typeof searchParams.order === "string"
      ? (searchParams.order as "asc" | "desc")
      : undefined

  const filters: PerformanceSummaryParams = {
    semester: semester === 0 ? null : semester,
    academic_year,
    subject_id,
    compare,
  }

  const res = await getFacultyPerformanceSummary(filters)
  if (!res.ok) {
    return <ErrorState title="Failed to load performance data" description={res.error.message} />
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight">Performance Analytics</h1>
        <p className="text-muted-foreground">
          Descriptive performance analytics with configurable learning-gap flags for everything you
          teach.
        </p>
      </div>
      <FreshnessStrip
        fetchedAt={res.fetchedAt}
        scopeLabel={buildScopeLabel(res.data.applied, res.data.filters)}
        filters={filters}
      />
      <PerformanceFilterBar
        filters={res.data.filters}
        hasPreviousTerm={res.data.previous_term !== null}
      />
      <PerformanceView data={res.data}>
        <Suspense fallback={sectionFallback()}>
          <ChartsSection filters={filters} thresholds={res.data.thresholds} />
        </Suspense>
        <Suspense fallback={sectionFallback()}>
          <InsightsSection filters={filters} />
        </Suspense>
        <Suspense fallback={sectionFallback()}>
          <LearningGapsSection filters={filters} />
        </Suspense>
        <Suspense fallback={sectionFallback()}>
          <StudentsSection
            filters={filters}
            search={search}
            gapStatus={gapStatus}
            page={page}
            sort={sort}
            order={order}
          />
        </Suspense>
      </PerformanceView>
    </div>
  )
}
