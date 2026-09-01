// Shared M3 V2 (At-Risk Student Prediction) client contract.
//
// Mirrors the backend production response schema in
// backend/app/schemas/m3v2.py. This model is shared by the student, faculty
// (mentorship), and admin BFF layers so the at-risk prediction surface renders
// consistently across roles.
//
// Integrity rules honored here (from the M3 V2 production discipline):
//   * probability_at_risk is a model ESTIMATE in [0, 1] of entering an academic
//     risk state (backlog/ATKT) in the next normal semester. It is NEVER a
//     guaranteed failure and must not be shown as "will fail".
//   * is_estimated_at_risk is a flag computed from the artifact's tuned
//     threshold — an estimate, not a diagnosis.
//   * signals are top features *contributing to the model estimate*, not causes.
//   * readiness_status is "READY" | "NO_DATA". A student with no upcoming
//     NORMAL academic semester (e.g. currently in the final / internship
//     semester 8) has readiness NO_DATA — the backend surfaces that as a 404.
//     This is the deliberate deployment boundary documented in the M3 V2
//     production report.

export type M3V2ReadinessStatus = "READY" | "NO_DATA"

export type M3V2Algorithm = Record<string, string>

export type M3V2Signal = {
  feature: string
  raw_value: number | null
  importance?: number | null
  log_odds_contribution?: number | null
}

export type M3V2PredictionData = {
  student_id: string
  model_id: string
  model_version: string
  readiness_status: M3V2ReadinessStatus
  observation_semester: number | null
  prediction_takes_effect_semester: number | null
  probability_at_risk: number | null
  threshold: number | null
  is_estimated_at_risk: boolean | null
  signals: M3V2Signal[]
  algorithm: M3V2Algorithm | null
  reason: string | null
  predicted_at: string
  inference_ms: number | null
  note: string
}

// Shared badge tone for an estimated at-risk probability. Higher risk maps to a
// more attention-grabbing tone; the wording stays "Estimated risk", never
// "will fail".
export function m3V2RiskTone(
  p: number | null,
): "success" | "secondary" | "warning" | "destructive" {
  if (p === null) return "secondary"
  if (p >= 0.5) return "destructive"
  if (p >= 0.3) return "warning"
  if (p >= 0.15) return "secondary"
  return "success"
}

// Human-friendly risk-level label derived from the model-estimated probability.
// This is a categorized presentation of the existing model output — it is NOT a
// calibrated confidence value and must never be presented as a guarantee.
export function riskLevelLabel(p: number | null): string {
  if (p === null) return "—"
  if (p >= 0.5) return "High"
  if (p >= 0.3) return "Moderate"
  if (p >= 0.15) return "Low-moderate"
  return "Low"
}

// Present the model-estimated probability as an integer percentage. Purely a
// formatting helper — the value shown always traces back to
// probability_at_risk.
export function formatRiskPercent(p: number | null): string {
  if (p === null) return "—"
  return `${Math.round(p * 100)}%`
}