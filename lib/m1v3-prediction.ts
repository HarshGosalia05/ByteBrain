// M1 V3 (Clean Subject Marks Prediction) client contract.
//
// Mirrors the backend production response schema in
// backend/app/schemas/m1v3.py. The clean model "m1_v3_clean"
// (HistGradientBoostingRegressor) uses the 38-feature
// "C_core_history_learning" contract (see ml/M1_v3_CampusX_package/
// schema/features.json).
//
// Subject-level input features exposed in the response:
//   internal_marks, mid_sem_marks, pre_endsem_assessment_pct,
//   assignment_score, quiz_avg_marks, submission_delay_days, credits.
// attendance_percentage is always null for this model (not an input of the
// clean model; retained for contract stability only).

export type M1V3ReadinessStatus = "READY" | "NO_DATA"

// Package-level constants sourced from M1_v3_METADATA.json.
export const M1V3_ALGO = "HistGradientBoostingRegressor"
export const M1V3_FEATURE_COUNT = 38
export const M1V3_FEATURE_SET = "C_core_history_learning"
export const M1V3_MODEL_VERSION = "m1_v3_clean"

export type M1V3SubjectInputFeatures = {
  internal_marks: number | null
  mid_sem_marks: number | null
  /** 0–100; pre-end-sem assessment aggregate. Null if not yet available. */
  pre_endsem_assessment_pct: number | null
  /** 0–100; continuous assessment (assignment) score. Null if not yet available. */
  assignment_score: number | null
  /** 0–100; average quiz marks. Null if not yet available. */
  quiz_avg_marks: number | null
  /** ≥0; total submission delay days. Null if not yet available. */
  submission_delay_days: number | null
  /** Always null for this model — not an input of the clean model. */
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

// University grade points specified:
// A+ = 10, A = 9, B+ = 8, B = 7, C = 6, D = 5, F = 0
export function m1V3GradePoint(band: string): number {
  switch (band.trim().toUpperCase()) {
    case "A+": return 10
    case "A":  return 9
    case "B+": return 8
    case "B":  return 7
    case "C":  return 6
    case "D":  return 5
    case "F":  return 0
    case "O":  return 10 // Handle legacy/alternate O grade band safely
    default:   return 0
  }
}

/**
 * Standard grade boundary mapping from percentage:
 * A+ (≥90%), A (≥80%), B+ (≥70%), B (≥60%), C (≥50%), D (≥40%), F (<40%)
 */
export function m1V3GradeFromPercentage(pct: number): string {
  if (pct >= 90) return "A+"
  if (pct >= 80) return "A"
  if (pct >= 70) return "B+"
  if (pct >= 60) return "B"
  if (pct >= 50) return "C"
  if (pct >= 40) return "D"
  return "F"
}

export type M1V3SubjectTotalCalculation = {
  internal: number
  midSem: number
  endSem: number
  totalMarks: number
  maxMarks: number
  percentage: number
  grade: string
  gradePoint: number
  credits: number
}

/**
 * Calculates a subject's total performance by combining components:
 * Internal (/20) + Mid-Sem (/50) + M1_v3 End-Sem (/70) = Total (/140)
 * → Predicted Percentage = (Total / 140) * 100
 * → Grade (A+, A, B+, B, C, D, F)
 * → Grade Point (A+=10, A=9, B+=8, B=7, C=6, D=5, F=0)
 */
export function m1V3SubjectTotal(
  subject: Pick<M1V3SubjectPrediction, "predicted_end_sem_marks" | "input_features">,
): M1V3SubjectTotalCalculation {
  const internal = subject.input_features.internal_marks ?? 0
  const midSem = subject.input_features.mid_sem_marks ?? 0
  const endSem = subject.predicted_end_sem_marks ?? 0
  const totalMarks = internal + midSem + endSem
  const maxMarks = 140 // 20 (internal) + 50 (mid-sem) + 70 (end-sem)
  const percentage = Math.min(100, Math.max(0, (totalMarks / maxMarks) * 100))
  const grade = m1V3GradeFromPercentage(percentage)
  const gradePoint = m1V3GradePoint(grade)
  const credits = subject.input_features.credits ?? 0

  return {
    internal,
    midSem,
    endSem,
    totalMarks,
    maxMarks,
    percentage,
    grade,
    gradePoint,
    credits,
  }
}

/**
 * Compute the credit-weighted SGPA from M1 V3 subject predictions.
 *
 * Formula:
 * 1. For each subject:
 *    Internal (/20) + Mid-Sem (/50) + M1_v3 End-Sem (/70)
 *    → Predicted Percentage = (Total / 140) * 100
 *    → Grade (A+, A, B+, B, C, D, F)
 *    → Grade Point (A+=10, A=9, B+=8, B=7, C=6, D=5, F=0)
 * 2. SGPA = Σ(Grade Point × Credits) / Σ(Credits)
 *
 * Subjects with missing or zero credits fall back to unweighted average.
 */
export function m1V3PredictedSGPA(
  subjects: Pick<M1V3SubjectPrediction, "predicted_end_sem_marks" | "input_features">[],
): number | null {
  if (!subjects || subjects.length === 0) return null

  let totalWeightedPoints = 0
  let totalCredits = 0
  let unweightedPoints = 0

  for (const s of subjects) {
    const calc = m1V3SubjectTotal(s)
    if (calc.credits > 0) {
      totalWeightedPoints += calc.credits * calc.gradePoint
      totalCredits += calc.credits
    }
    unweightedPoints += calc.gradePoint
  }

  if (totalCredits > 0) {
    return Number((totalWeightedPoints / totalCredits).toFixed(2))
  }
  if (subjects.length > 0) {
    return Number((unweightedPoints / subjects.length).toFixed(2))
  }
  return null
}

/**
 * Compute credit-weighted predicted semester percentage from M1 V3 subject predictions.
 *
 * Formula:
 * Pct = Σ(Percentage × Credits) / Σ(Credits)
 * where Percentage = (Internal + Mid-Sem + End-Sem) / 140 * 100
 */
export function m1V3PredictedPercentage(
  subjects: Pick<M1V3SubjectPrediction, "predicted_end_sem_marks" | "input_features">[],
): number | null {
  if (!subjects || subjects.length === 0) return null

  let totalWeightedPct = 0
  let totalCredits = 0
  let unweightedPct = 0

  for (const s of subjects) {
    const calc = m1V3SubjectTotal(s)
    if (calc.credits > 0) {
      totalWeightedPct += calc.credits * calc.percentage
      totalCredits += calc.credits
    }
    unweightedPct += calc.percentage
  }

  if (totalCredits > 0) {
    return Number((totalWeightedPct / totalCredits).toFixed(1))
  }
  if (subjects.length > 0) {
    return Number((unweightedPct / subjects.length).toFixed(1))
  }
  return null
}


