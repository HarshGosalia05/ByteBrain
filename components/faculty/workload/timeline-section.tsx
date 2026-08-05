import { getFacultyWorkloadTimeline } from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { TimelineView } from "./timeline-view"

export async function TimelineSection() {
  const result = await getFacultyWorkloadTimeline()
  return <TimelineView data={toSectionResult(result)} />
}
