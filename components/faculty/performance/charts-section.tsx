import {
  getFacultyPerformanceDistributions,
  getFacultyPerformanceSubjectBreakdown,
  getFacultyPerformanceTrends,
  type PerformanceSummaryParams,
  type PerformanceThresholds,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { ChartsView } from "./charts-view"

export async function ChartsSection({
  filters,
  thresholds,
}: {
  filters: PerformanceSummaryParams
  thresholds: PerformanceThresholds
}) {
  const [distributions, subjectBreakdown, trends] = await Promise.allSettled([
    getFacultyPerformanceDistributions(filters),
    getFacultyPerformanceSubjectBreakdown(filters),
    getFacultyPerformanceTrends(filters),
  ])

  return (
    <ChartsView
      distributions={toSectionResult(distributions)}
      subjectBreakdown={toSectionResult(subjectBreakdown)}
      trends={toSectionResult(trends)}
      thresholds={thresholds}
    />
  )
}
