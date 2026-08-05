import {
  getFacultyWorkloadHighlights,
  type WorkloadSummaryParams,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { HighlightsView } from "./highlights-view"

export async function HighlightsSection({ filters }: { filters: WorkloadSummaryParams }) {
  const result = await getFacultyWorkloadHighlights(filters)
  return <HighlightsView data={toSectionResult(result)} />
}
