import { Sparkles, CircleAlert } from "lucide-react"

import { EmptyState } from "@/components/shared/state/empty-state"
import type { M1V2PredictionData } from "@/lib/m1v2-prediction"
import type { M1V3PredictionData } from "@/lib/m1v3-prediction"
import type { M2V2PredictionData } from "@/lib/m2v2-prediction"
import type { M3V2PredictionData } from "@/lib/m3v2-prediction"
import type { StudentCareerGuidance, StudentMlInsights } from "@/lib/student-api"

import { M1V2Card } from "./m1v2-card"
import { M1V3Card } from "./m1v3-card"
import { M2V2Card } from "./m2v2-card"
import { M3V2Card } from "./m3v2-card"
import { M4CareerGuidanceCard } from "./m4-career-guidance-card"
import { M4InsightsCard } from "./m4-insights-card"

function V2NoDataNote({ title, message }: { title: string; message: string }) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-4"
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div className="flex flex-col gap-0.5">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs leading-relaxed text-muted-foreground">{message}</p>
      </div>
    </div>
  )
}

function hasAnyData(
  insights: StudentMlInsights,
  guidance: StudentCareerGuidance | null,
  m1v2: M1V2PredictionData | null,
  m1v2NoData: boolean,
  m1v3: M1V3PredictionData | null,
  m1v3NoData: boolean,
  m2v2: M2V2PredictionData | null,
  m2v2NoData: boolean,
  m3v2: M3V2PredictionData | null,
  m3v2NoData: boolean,
): boolean {
  const m4Available = insights.models.m4?.available ?? false
  return (
    m4Available ||
    (guidance?.data_available ?? false) ||
    m1v2NoData ||
    m1v3NoData ||
    m2v2NoData ||
    m3v2NoData ||
    (m1v2?.subjects.length ?? 0) > 0 ||
    (m1v3?.subjects.length ?? 0) > 0 ||
    (m2v2?.readiness_status ?? "") === "READY" ||
    (m3v2?.readiness_status ?? "") === "READY"
  )
}

export function MlInsightsGrid({
  data,
  guidance = null,
  m1v2 = null,
  m1v2NoData = false,
  m1v2Reason = null,
  m1v3 = null,
  m1v3NoData = false,
  m1v3Reason = null,
  m2v2 = null,
  m2v2NoData = false,
  m3v2 = null,
  m3v2NoData = false,
}: {
  data: StudentMlInsights
  guidance?: StudentCareerGuidance | null
  m1v2?: M1V2PredictionData | null
  m1v2NoData?: boolean
  m1v2Reason?: string | null
  m1v3?: M1V3PredictionData | null
  m1v3NoData?: boolean
  m1v3Reason?: string | null
  m2v2?: M2V2PredictionData | null
  m2v2NoData?: boolean
  m3v2?: M3V2PredictionData | null
  m3v2NoData?: boolean
}) {
  if (!hasAnyData(data, guidance, m1v2, m1v2NoData, m1v3, m1v3NoData, m2v2, m2v2NoData, m3v2, m3v2NoData)) {
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
      {m1v3 && <M1V3Card data={m1v3} />}
      {m1v3NoData && !m1v3 && (
        <V2NoDataNote
          title="Prediction unavailable"
          message={m1v3Reason ?? "Not enough current-semester academic data is available to generate a reliable subject prediction yet."}
        />
      )}
      {!m1v3 && m1v2 && <M1V2Card data={m1v2} />}
      {!m1v3 && m1v2NoData && !m1v2 && (
        <V2NoDataNote
          title="Prediction unavailable"
          message={m1v2Reason ?? "Not enough current-semester academic data is available to generate a reliable subject prediction yet."}
        />
      )}
      {m2v2 && <M2V2Card data={m2v2} />}
      {m2v2NoData && !m2v2 && (
        <V2NoDataNote
          title="Next-semester prediction not available"
          message="A next-semester prediction is not available because a future academic semester is not currently available in the dataset."
        />
      )}
      {m3v2 && <M3V2Card data={m3v2} />}
      {m3v2NoData && !m3v2 && (
        <V2NoDataNote
          title="Academic risk estimate not available"
          message="An academic risk estimate is not available because a future academic semester is not currently available in the dataset."
        />
      )}
      <M4InsightsCard model={data.models.m4} />
      <M4CareerGuidanceCard guidance={guidance} />
    </div>
  )
}
