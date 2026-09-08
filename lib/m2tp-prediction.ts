/**
 * Shared TypeScript contract for the M2-TP next-semester Theory & Practical
 * performance prediction endpoint (/api/v1/predict/m2tp/{student_id}).
 */

export type M2TPSubjectTypePrediction = {
  readiness_status: "READY" | "NO_DATA"
  predicted_percentage: number | null
  target_subject_count: number
  feature_count: number
  algorithm?: string | null
  reason?: string | null
}

export type M2TPPredictionData = {
  student_id: string
  model_id: "m2_tp"
  model_version: string
  readiness_status: "READY" | "NO_DATA"
  observation_semester: number | null
  target_semester: number | null
  theory: M2TPSubjectTypePrediction
  practical: M2TPSubjectTypePrediction
  reason?: string | null
  predicted_at: string
  inference_ms?: number | null
  note?: string
}

/**
 * Return a UI badge tone for a predicted percentage.
 */
export function m2tpPerformanceTone(
  percentage: number | null,
): "default" | "secondary" | "destructive" | "outline" {
  if (percentage === null) return "secondary"
  if (percentage >= 75) return "default"
  if (percentage >= 60) return "secondary"
  return "destructive"
}
