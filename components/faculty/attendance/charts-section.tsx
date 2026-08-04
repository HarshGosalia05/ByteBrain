import {
  getFacultyAttendanceCorrelation,
  getFacultyAttendanceDistributions,
  getFacultyAttendanceSubjectBreakdown,
  getFacultyAttendanceTrends,
  type AttendanceSummaryParams,
  type AttendanceThresholds,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { ChartsView } from "./charts-view"

export async function ChartsSection({
  filters,
  thresholds,
}: {
  filters: AttendanceSummaryParams
  thresholds: AttendanceThresholds
}) {
  const [distributions, subjectBreakdown, trends, correlation] = await Promise.allSettled([
    getFacultyAttendanceDistributions(filters),
    getFacultyAttendanceSubjectBreakdown(filters),
    getFacultyAttendanceTrends(filters),
    getFacultyAttendanceCorrelation(filters),
  ])

  return (
    <ChartsView
      distributions={toSectionResult(distributions)}
      subjectBreakdown={toSectionResult(subjectBreakdown)}
      trends={toSectionResult(trends)}
      correlation={toSectionResult(correlation)}
      thresholds={thresholds}
    />
  )
}
