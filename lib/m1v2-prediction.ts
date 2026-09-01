// Shared M1 V2 (Subject Marks Prediction) client contract.
//
// Mirrors the backend production response schema in
// backend/app/schemas/m1v2.py. This model is shared by the student, faculty
// (mentorship), and admin BFF layers so the prediction surface renders
// consistently across roles.
//
// Integrity rules honored here (from the M1 V2 production report):
//   * predicted_end_sem_marks is a model estimate in [0, 70] — never a real
//     academic result.
//   * No confidence bands are fabricated: the ridge model exposes no
//     calibrated uncertainty, so they are intentionally absent.
//   * readiness_status is "READY" | "NO_DATA".

export type M1V2ReadinessStatus = "READY" | "NO_DATA"

export type M1V2SubjectInputFeatures = {
  internal_marks: number | null
  mid_sem_marks: number | null
  att_total_pct: number | null
  pre_endsem_assessment_pct: number | null
}

export type M1V2SubjectPrediction = {
  subject_id: string
  semester_no: number
  predicted_end_sem_marks: number
  target_max: number
  grade_band: string
  grade_label: string
  input_features: M1V2SubjectInputFeatures
}

export type M1V2PredictionData = {
  student_id: string
  model_id: string
  model_version: string
  algorithm: string | null
  readiness_status: M1V2ReadinessStatus
  current_semester: number | null
  prediction_count: number
  predicted_at: string
  inference_ms: number | null
  subjects: M1V2SubjectPrediction[]
  note: string | null
}

// Shared badge tone for an M1 V2 grade band.
//
// The M1 V2 backend derives grade_band as the grade letter from predicted
// end-sem marks (see ml/v2/m1_subject_prediction/inference/predictor.py
// `_grade_from_marks`): O / A+ / A / B+ / B / C / F. The tone maps each band to
// a badge variant so a higher band renders as more encouraging and a failing
// band is flagged for attention. Bands are a presentation mapping of the model
// estimate, not a claim of a real result.
export function m1V2GradeTone(
  band: string,
): "success" | "secondary" | "warning" | "destructive" {
  const normalized = band.trim().toUpperCase()
  if (normalized === "O" || normalized === "A+" || normalized === "A" || normalized === "B+")
    return "success"
  if (normalized === "B") return "secondary"
  if (normalized === "C") return "warning"
  return "destructive"
}

