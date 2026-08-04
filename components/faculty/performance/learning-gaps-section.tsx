import {
  getFacultyPerformanceLearningGaps,
  type PerformanceSummaryParams,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { LearningGapsView } from "./learning-gaps-view"

export async function LearningGapsSection({ filters }: { filters: PerformanceSummaryParams }) {
  const result = await getFacultyPerformanceLearningGaps(filters)
  return <LearningGapsView data={toSectionResult(result)} />
}
