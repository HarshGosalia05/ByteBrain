// Shared M2 V2 (Next-Semester Performance Prediction) client contract.
//
// Mirrors the backend production response schema in
// backend/app/schemas/m2v2.py. This model is shared by the student, faculty
// (mentorship), and admin BFF layers so the prediction surface renders
// consistently across roles.
//
// Integrity rules honored here (from the M2 V2 production discipline):
//   * predicted_next_semester_sgpa is a model estimate in [0, 10];
//     predicted_next_semester_percentage in [0, 100] — never real results.
//   * readiness_status is "READY" | "NO_DATA".
//   * A student with no upcoming NORMAL academic semester (e.g. currently in
//     the final / internship semester 8) has readiness NO_DATA — the backend
//     surfaces that as a 404. No fabricated forward prediction is shown.
//     This is the deliberate deployment boundary documented in the M2 V2
//     production report: the model serves earlier-semester students / future
//     cohorts.

export type M2V2ReadinessStatus = "READY" | "NO_DATA"

export type M2V2Algorithm = Record<string, string>

export type M2V2PredictionData = {
  student_id: string
  model_id: string
  model_version: string
  readiness_status: M2V2ReadinessStatus
  observation_semester: number | null
  prediction_takes_effect_semester: number | null
  predicted_next_semester_sgpa: number | null
  predicted_next_semester_percentage: number | null
  algorithm: M2V2Algorithm | null
  reason: string | null
  predicted_at: string
  inference_ms: number | null
  note: string
}

// Shared badge tone for a predicted next-semester SGPA. A higher predicted SGPA
// maps to a more encouraging tone; lower values are flagged for attention.
export function m2V2SgpaTone(
  sgpa: number | null,
): "success" | "secondary" | "warning" | "destructive" {
  if (sgpa === null) return "secondary"
  if (sgpa >= 7.5) return "success"
  if (sgpa >= 6.5) return "secondary"
  if (sgpa >= 5.5) return "warning"
  return "destructive"
}