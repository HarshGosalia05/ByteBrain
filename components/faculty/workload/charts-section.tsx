import {
  getFacultyWorkloadBenchmark,
  getFacultyWorkloadCapacity,
  getFacultyWorkloadForecast,
  getFacultyWorkloadMatrices,
  getFacultyWorkloadScatter,
  getFacultyWorkloadSubjectBreakdown,
  getFacultyWorkloadTrends,
  type WorkloadSummaryParams,
  type WorkloadThresholds,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { ChartsView } from "./charts-view"

export async function ChartsSection({
  filters,
  thresholds,
}: {
  filters: WorkloadSummaryParams
  thresholds: WorkloadThresholds
}) {
  const [subjectBreakdown, trends, capacity, matrices, scatter, benchmark, forecast] =
    await Promise.allSettled([
      getFacultyWorkloadSubjectBreakdown(filters),
      getFacultyWorkloadTrends(filters),
      getFacultyWorkloadCapacity(filters),
      getFacultyWorkloadMatrices(filters),
      getFacultyWorkloadScatter(filters),
      getFacultyWorkloadBenchmark(filters),
      getFacultyWorkloadForecast(),
    ])

  return (
    <ChartsView
      subjectBreakdown={toSectionResult(subjectBreakdown)}
      trends={toSectionResult(trends)}
      capacity={toSectionResult(capacity)}
      matrices={toSectionResult(matrices)}
      scatter={toSectionResult(scatter)}
      benchmark={toSectionResult(benchmark)}
      forecast={toSectionResult(forecast)}
      thresholds={thresholds}
    />
  )
}
