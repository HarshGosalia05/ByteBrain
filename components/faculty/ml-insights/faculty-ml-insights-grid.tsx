import { Sparkles } from "lucide-react"

import { EmptyState } from "@/components/shared/state/empty-state"
import { facultyMlAvailableCount, type FacultyStudentMlInsights } from "@/lib/faculty-api"

import { M1InsightsCard } from "./m1-insights-card"
import { M2InsightsCard } from "./m2-insights-card"
import { M3InsightsCard } from "./m3-insights-card"
import { M4InsightsCard } from "./m4-insights-card"

export function FacultyMlInsightsGrid({
  data,
  studentId,
}: {
  data: FacultyStudentMlInsights
  studentId: string
}) {
  const availableCount = facultyMlAvailableCount(data.models)

  if (availableCount === 0) {
    return (
      <EmptyState
        icon={Sparkles}
        title="No predictions available for this student"
        description="Once the student's academic records are complete, predictions and grounded explanations will appear here."
      />
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <M1InsightsCard model={data.models.m1} />
      <div className="grid gap-6 lg:grid-cols-2">
        <M2InsightsCard model={data.models.m2} />
        <M3InsightsCard model={data.models.m3} studentId={studentId} />
      </div>
      <M4InsightsCard model={data.models.m4} />
    </div>
  )
}
