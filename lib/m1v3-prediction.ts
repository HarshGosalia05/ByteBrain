// M1 V3 (Synthetic-trained Subject Marks Prediction) client contract.
//
// Mirrors the backend production response schema in
// backend/app/schemas/m1v3.py. Uses 8 features:
//   internal_marks, mid_sem_marks, attendance_percentage, credits,
//   semester_no, subject_type, department_name, gender
//
// Attendance is sourced from the attendance.attendance_percentage column.

export type M1V3ReadinessStatus = "READY" | "NO_DATA"

export type M1V3SubjectInputFeatures = {
  internal_marks: number | null
  mid_sem_marks: number | null
  attendance_percentage: number | null
  credits: number | null
}

export type M1V3SubjectPrediction = {
  subject_id: string
  subject_name: string | null
  semester_no: number
  predicted_end_sem_marks: number
  target_max: number
  grade_band: string
  grade_label: string
  input_features: M1V3SubjectInputFeatures
}

export type M1V3PredictionData = {
  student_id: string
  model_id: string
  model_version: string
  algorithm: string | null
  readiness_status: M1V3ReadinessStatus
  reason: string | null
  current_semester: number | null
  prediction_count: number
  predicted_at: string
  inference_ms: number | null
  subjects: M1V3SubjectPrediction[]
  note: string | null
}

// The M1 V3 model predicts end-sem marks on the 0-70 scale (TARGET_MAX in the
// backend predictor). The "Current" tile shows the student's verified mid-sem
// marks stored in student_subject_performance.mid_sem_marks, which use a
// 0-50 scale. The two scales must never be subtracted or shown with a shared
// denominator.
export const M1V3_PREDICTED_MAX = 70
export const M1V3_MID_SEM_MAX = 50

// The predicted end-sem mark is rendered verbatim from the M1 V3 model output.
export function m1V3PredictedEndSem(item: M1V3SubjectPrediction): number {
  return item.predicted_end_sem_marks
}

// The "Current" tile is sourced exclusively from the authenticated student's
// verified mid-sem marks (input_features.mid_sem_marks) on their raw 0-50
// scale. No prediction, M2, percentage, SGPA, or internal marks are used.
// There is deliberately no delta helper: predicted (/70) and current (/50)
// share no denominator.
export function m1V3CurrentMidSem(item: M1V3SubjectPrediction): {
  value: number | null
  max: number
} {
  const mid = item.input_features.mid_sem_marks
  return { value: mid ?? null, max: M1V3_MID_SEM_MAX }
}

// Shared grade tone mapping (same logic as M1 V2).
export function m1V3GradeTone(
  band: string,
): "success" | "secondary" | "warning" | "destructive" {
  const normalized = band.trim().toUpperCase()
  if (normalized === "O" || normalized === "A+" || normalized === "A" || normalized === "B+")
    return "success"
  if (normalized === "B") return "secondary"
  if (normalized === "C") return "warning"
  return "destructive"
}
