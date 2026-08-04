import {
  getFacultyAttendanceGovernance,
  getFacultyAttendanceHealthScore,
  type AttendanceSummaryParams,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { GovernanceView } from "./governance-view"

export async function GovernanceSection({
  filters,
}: {
  filters: AttendanceSummaryParams
}) {
  const [governance, healthScore] = await Promise.allSettled([
    getFacultyAttendanceGovernance(filters),
    getFacultyAttendanceHealthScore(filters),
  ])

  return (
    <GovernanceView
      governance={toSectionResult(governance)}
      healthScore={toSectionResult(healthScore)}
    />
  )
}
