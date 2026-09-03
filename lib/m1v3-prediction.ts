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
