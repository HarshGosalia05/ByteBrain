import {
  getFacultyAttendanceHighlights,
  type AttendanceSummaryParams,
} from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { HighlightsView } from "./highlights-view"

export async function HighlightsSection({ filters }: { filters: AttendanceSummaryParams }) {
  const result = await getFacultyAttendanceHighlights(filters)
  return <HighlightsView data={toSectionResult(result)} />
}
