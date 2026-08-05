import {
  getFacultyWorkloadGovernance,
  getFacultyWorkloadHealthScore,
  type WorkloadSummaryParams,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { GovernanceView } from "./governance-view"

export async function GovernanceSection({ filters }: { filters: WorkloadSummaryParams }) {
  const [governance, healthScore] = await Promise.allSettled([
    getFacultyWorkloadGovernance(filters),
    getFacultyWorkloadHealthScore(filters),
  ])

  return (
    <GovernanceView
      governance={toSectionResult(governance)}
      healthScore={toSectionResult(healthScore)}
    />
  )
}
