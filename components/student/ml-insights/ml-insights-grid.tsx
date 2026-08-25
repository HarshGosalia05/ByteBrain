import { Sparkles } from "lucide-react"

import { EmptyState } from "@/components/shared/state/empty-state"
import type { StudentCareerGuidance, StudentMlInsights } from "@/lib/student-api"

import { M1InsightsCard } from "./m1-insights-card"
import { M2InsightsCard } from "./m2-insights-card"
import { M3InsightsCard } from "./m3-insights-card"
import { M4CareerGuidanceCard } from "./m4-career-guidance-card"
import { M4InsightsCard } from "./m4-insights-card"

export function MlInsightsGrid({
  data,
  guidance = null,
}: {
  data: StudentMlInsights
  guidance?: StudentCareerGuidance | null
}) {
  const availableCount = Object.values(data.models).filter((model) => model.available).length

  if (availableCount === 0 && !(guidance && guidance.data_available)) {
    return (
      <EmptyState
        icon={Sparkles}
        title="No predictions available yet"
        description="Once your academic records are complete, personalised predictions and explanations will appear here."
      />
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <M1InsightsCard model={data.models.m1} />
      <div className="grid gap-6 lg:grid-cols-2">
        <M2InsightsCard model={data.models.m2} />
        <M3InsightsCard model={data.models.m3} />
      </div>
      <M4InsightsCard model={data.models.m4} />
      <M4CareerGuidanceCard guidance={guidance} />
    </div>
  )
}
