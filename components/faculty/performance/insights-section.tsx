import {
  getFacultyPerformanceInsights,
  type PerformanceSummaryParams,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { InsightsView } from "./insights-view"

export async function InsightsSection({ filters }: { filters: PerformanceSummaryParams }) {
  const result = await getFacultyPerformanceInsights(filters)
  return <InsightsView data={toSectionResult(result)} />
}
