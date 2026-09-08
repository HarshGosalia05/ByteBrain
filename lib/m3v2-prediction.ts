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

// Human-readable labels for the raw model feature names surfaced in `signals`
// (see ml/v2/m3_at_risk_prediction/config.py for the feature tiers). The raw
// feature keys are internal ML names and are never shown verbatim to users.
export const M3V2_FEATURE_LABELS: Record<string, string> = {
  // Tier 1A — current-semester (T) summary outcomes
  semester_sgpa: "Latest Semester SGPA",
  semester_percentage: "Latest Semester Percentage",
  semester_total_marks: "Latest Semester Total Marks",
  semester_attendance_percentage: "Latest Semester Attendance",
  backlog_count: "Current Active Backlogs",
  cumulative_backlog_events: "Cumulative Backlog Events",
  credits_registered: "Credits Registered",
  credits_earned: "Credits Earned",
  subjects_registered: "Subjects Registered",
  // Tier 1B — point-in-time prior history
  previous_sem_sgpa: "Previous Semester SGPA",
  sgpa_drift: "SGPA Drift vs Previous Semester",
  sgpa_rolling_mean_3: "Recent 3-Semester SGPA",
  previous_sem_backlog_count: "Previous Semester Backlogs",
  backlog_change: "Backlog Count Change",
  attendance_aggregate_pct: "Aggregate Attendance Percentage",
  // Tier 1C — subject-level aggregates at T
  subj_internal_marks_mean: "Average Internal Marks",
  subj_internal_marks_std: "Internal Marks Variation",
  subj_mid_sem_marks_mean: "Average Mid-Semester Marks",
  subj_end_sem_marks_mean: "Average End-Semester Marks",
  subj_end_sem_marks_std: "End-Semester Marks Variation",
  subj_assignment_score_mean: "Average Assignment Score",
  subj_quiz_avg_marks_mean: "Average Quiz Marks",
  subj_submission_delay_mean: "Average Submission Delay (Days)",
  subj_pre_endsem_pct_mean: "Pre-End-Sem Assessment %",
  subj_failed_subjects_count: "Failed Subjects Count",
  // Tier 1D — attendance aggregates at T
  att_tsem_total_pct: "Semester Attendance %",
  att_tsem_low_pct_weeks: "Low Attendance Weeks Ratio",
  att_tsem_velocity_mean: "Attendance Trend Velocity",
  // Tier 1E — learning activity aggregates at T
  learn_tsem_volume_total: "Total Learning Activity Volume",
  learn_tsem_engagement_mean: "Learning Engagement Consistency",
  learn_tsem_completion_mean: "Assessment Completion Rate",
  learn_tsem_late_mean: "Late Submission Rate",
  // Tier 1F — student / lifestyle metadata
  is_male: "Gender (Coded)",
  semester_no: "Observation Semester",
  stress_ordinal: "Stress Level (Coded)",
  study_hours_per_week: "Weekly Study Hours",
}

// Render the raw feature value with a human-readable unit when the unit is
// unambiguous; otherwise fall back to a plain numeric format.
export function m3V2FeatureLabel(feature: string): string {
  return M3V2_FEATURE_LABELS[feature] ?? feature
}

export function m3V2SignalValue(signal: M3V2Signal): string {
  const raw = signal.raw_value
  if (raw === null || raw === undefined || Number.isNaN(raw)) return "Not available"
  const v = Number(raw)
  if (M3V2_PERCENT_FEATURES.has(signal.feature)) return `${v.toFixed(2)}%`
  if (M3V2_SGPA_FEATURES.has(signal.feature)) return v.toFixed(2)
  if (M3V2_INTEGER_FEATURES.has(signal.feature)) return String(Math.round(v))
  return v.toFixed(2)
}

const M3V2_PERCENT_FEATURES = new Set([
  "semester_percentage",
  "semester_attendance_percentage",
  "attendance_aggregate_pct",
  "att_tsem_total_pct",
  "subj_pre_endsem_pct_mean",
])

const M3V2_SGPA_FEATURES = new Set([
  "semester_sgpa",
  "previous_sem_sgpa",
  "sgpa_drift",
  "sgpa_rolling_mean_3",
])

const M3V2_INTEGER_FEATURES = new Set([
  "subjects_registered",
  "credits_registered",
  "credits_earned",
  "backlog_count",
  "cumulative_backlog_events",
  "previous_sem_backlog_count",
  "subj_failed_subjects_count",
  "learn_tsem_volume_total",
  "is_male",
  "semester_no",
])