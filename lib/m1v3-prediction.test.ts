// Frontend tests for the M1 V3 subject-prediction card contract helpers.
//
// Runs with Node's built-in test runner + TypeScript type stripping:
//   node --experimental-test-module-mocks --test lib/m1v3-prediction.test.ts
//
// These helpers are pure-presentation mappings of the backend model output.
// Rules that must never regress:
//   - Predicted end-sem marks are rendered verbatim on the /70 (target_max) scale.
//   - "Current" is sourced exclusively from the verified mid-sem marks
//     (input_features.mid_sem_marks) on their raw /50 scale. It must never use
//     internal marks, the prediction, an M2/SGPA value, or a percentage.
//   - The two scales share no denominator, so no diff/delta is ever computed.

import { test } from "node:test"
import assert from "node:assert/strict"

import {
  M1V3_MID_SEM_MAX,
  M1V3_PREDICTED_MAX,
  m1V3CurrentMidSem,
  m1V3GradeFromPercentage,
  m1V3GradePoint,
  m1V3GradeTone,
  m1V3PredictedEndSem,
  m1V3PredictedPercentage,
  m1V3PredictedSGPA,
  m1V3SubjectTotal,
  type M1V3SubjectPrediction,
} from "./m1v3-prediction.ts"

// STU000002-style fixtures: internal marks are /20, mid-sem marks are /50.
const deepLearning: M1V3SubjectPrediction = {
  subject_id: "SUB0053",
  subject_name: "Deep Learning",
  semester_no: 7,
  predicted_end_sem_marks: 57.38,
  target_max: 70,
  grade_band: "A+",
  grade_label: "Excellent",
  input_features: {
    internal_marks: 18,
    mid_sem_marks: 49,
    pre_endsem_assessment_pct: 75.0,
    assignment_score: 82.0,
    quiz_avg_marks: 78.0,
    submission_delay_days: 0.5,
    attendance_percentage: null,
    credits: 4,
  },
}

const deepLearningLab: M1V3SubjectPrediction = {
  subject_id: "SUB0057",
  subject_name: "Deep Learning Laboratory",
  semester_no: 7,
  predicted_end_sem_marks: 53.4,
  target_max: 70,
  grade_band: "A",
  grade_label: "Very good",
  input_features: {
    internal_marks: 12,
    mid_sem_marks: 41,
    pre_endsem_assessment_pct: 60.0,
    assignment_score: null,
    quiz_avg_marks: null,
    submission_delay_days: null,
    attendance_percentage: null,
    credits: 2,
  },
}

// ---------------------------------------------------------------------------
// Predicted end-sem marks stay on the /70 scale, verbatim from the model
// ---------------------------------------------------------------------------

test("predicted end-sem marks are rendered on the /70 target_max scale", () => {
  assert.equal(M1V3_PREDICTED_MAX, 70)
  assert.equal(deepLearning.target_max, M1V3_PREDICTED_MAX)
  assert.equal(deepLearningLab.target_max, M1V3_PREDICTED_MAX)
})

test("predicted values are returned unchanged from the model output", () => {
  assert.equal(m1V3PredictedEndSem(deepLearning), 57.38)
  assert.equal(m1V3PredictedEndSem(deepLearningLab), 53.4)
})

// ---------------------------------------------------------------------------
// "Current" is the verified mid-sem mark on its raw /50 scale
// ---------------------------------------------------------------------------

test("current scale is the raw mid-sem /50 scale, never /70 or /20", () => {
  assert.equal(M1V3_MID_SEM_MAX, 50)
  assert.equal(m1V3CurrentMidSem(deepLearning).max, 50)
  assert.equal(m1V3CurrentMidSem(deepLearning).max, M1V3_MID_SEM_MAX)
  assert.notEqual(m1V3CurrentMidSem(deepLearning).max, M1V3_PREDICTED_MAX)
})

test("current value comes from the verified mid-sem marks, not internal marks", () => {
  const current = m1V3CurrentMidSem(deepLearning)
  assert.equal(current.value, 49)
  assert.notEqual(current.value, deepLearning.input_features.internal_marks) // 18, not 49
})

test("current value never uses the predicted end-sem mark", () => {
  const current = m1V3CurrentMidSem(deepLearning)
  assert.notEqual(current.value, deepLearning.predicted_end_sem_marks)
  assert.equal(current.value, deepLearning.input_features.mid_sem_marks)
})

test("empty mid-sem marks render as a null placeholder, not a fabricated value", () => {
  const missing: M1V3SubjectPrediction = {
    ...deepLearning,
    input_features: { ...deepLearning.input_features, mid_sem_marks: null },
  }
  assert.deepEqual(m1V3CurrentMidSem(missing), { value: null, max: M1V3_MID_SEM_MAX })
})

// ---------------------------------------------------------------------------
// Per-subject separation (Deep Learning vs Deep Learning Laboratory)
// ---------------------------------------------------------------------------

test("each subject tile keeps its own verified mid-sem value", () => {
  const dl = m1V3CurrentMidSem(deepLearning)
  const lab = m1V3CurrentMidSem(deepLearningLab)
  assert.equal(dl.value, 49)
  assert.equal(lab.value, 41)
  assert.notEqual(dl.value, lab.value)
})

// ---------------------------------------------------------------------------
// No cross-scale delta, no M2 involvement
// ---------------------------------------------------------------------------

test("current output exposes only value and max — no diff/delta field", () => {
  assert.deepEqual(Object.keys(m1V3CurrentMidSem(deepLearning)).sort(), ["max", "value"])
})

test("current output never carries an M2/SGPA or percentage field", () => {
  const output = m1V3CurrentMidSem(deepLearning)
  const serialized = JSON.stringify(output)
  assert.ok(!serialized.includes("sgpa"))
  assert.ok(!serialized.includes("predicted_next"))
  assert.ok(!serialized.includes("percentage"))
})

// ---------------------------------------------------------------------------
// Grade tone stays intact
// ---------------------------------------------------------------------------

test("m1V3GradeTone maps top bands to success (unchanged)", () => {
  assert.equal(m1V3GradeTone("A+"), "success")
  assert.equal(m1V3GradeTone("A"), "success")
  assert.equal(m1V3GradeTone("O"), "success")
})

// ---------------------------------------------------------------------------
// Grade points and percentage scale
// ---------------------------------------------------------------------------

test("m1V3GradePoint follows university scale: A+=10, A=9, B+=8, B=7, C=6, D=5, F=0", () => {
  assert.equal(m1V3GradePoint("A+"), 10)
  assert.equal(m1V3GradePoint("A"), 9)
  assert.equal(m1V3GradePoint("B+"), 8)
  assert.equal(m1V3GradePoint("B"), 7)
  assert.equal(m1V3GradePoint("C"), 6)
  assert.equal(m1V3GradePoint("D"), 5)
  assert.equal(m1V3GradePoint("F"), 0)
  assert.equal(m1V3GradePoint("O"), 10)
  assert.equal(m1V3GradePoint("unknown"), 0)
})

test("m1V3GradeFromPercentage maps standard percentage tiers", () => {
  assert.equal(m1V3GradeFromPercentage(95), "A+")
  assert.equal(m1V3GradeFromPercentage(90), "A+")
  assert.equal(m1V3GradeFromPercentage(89.9), "A")
  assert.equal(m1V3GradeFromPercentage(80), "A")
  assert.equal(m1V3GradeFromPercentage(75), "B+")
  assert.equal(m1V3GradeFromPercentage(65), "B")
  assert.equal(m1V3GradeFromPercentage(55), "C")
  assert.equal(m1V3GradeFromPercentage(45), "D")
  assert.equal(m1V3GradeFromPercentage(35), "F")
})

// ---------------------------------------------------------------------------
// Predicted SGPA calculation pipeline:
// Internal (/20) + Mid-Sem (/50) + M1_v3 End-Sem (/70) -> Total (/140)
// -> Predicted Percentage -> Grade -> Grade Point -> Credit-weighted SGPA
// ---------------------------------------------------------------------------

test("m1V3SubjectTotal combines Internal + Mid + End-Sem correctly", () => {
  // deepLearning: int 18/20, mid 49/50, end 57.38/70
  // total = 18 + 49 + 57.38 = 124.38/140 = 88.84% -> Grade A (GP 9)
  const calc = m1V3SubjectTotal(deepLearning)
  assert.equal(calc.internal, 18)
  assert.equal(calc.midSem, 49)
  assert.equal(calc.endSem, 57.38)
  assert.equal(calc.totalMarks, 124.38)
  assert.equal(calc.maxMarks, 140)
  assert.ok(Math.abs(calc.percentage - 88.84) < 0.05)
  assert.equal(calc.grade, "A")
  assert.equal(calc.gradePoint, 9)
  assert.equal(calc.credits, 4)
})

test("m1V3SubjectTotal calculates lab subject correctly", () => {
  // deepLearningLab: int 12/20, mid 41/50, end 53.4/70
  // total = 12 + 41 + 53.4 = 106.4/140 = 76.0% -> Grade B+ (GP 8)
  const calc = m1V3SubjectTotal(deepLearningLab)
  assert.equal(calc.internal, 12)
  assert.equal(calc.midSem, 41)
  assert.equal(calc.endSem, 53.4)
  assert.equal(calc.totalMarks, 106.4)
  assert.equal(calc.maxMarks, 140)
  assert.ok(Math.abs(calc.percentage - 76.0) < 0.05)
  assert.equal(calc.grade, "B+")
  assert.equal(calc.gradePoint, 8)
  assert.equal(calc.credits, 2)
})

test("m1V3PredictedSGPA computes credit-weighted SGPA: Σ(GP × Cr) / Σ(Cr)", () => {
  // DL: GP 9, credits 4 -> 36
  // Lab: GP 8, credits 2 -> 16
  // Total Cr = 6, Total WP = 52 -> SGPA = 52 / 6 = 8.67
  const sgpa = m1V3PredictedSGPA([deepLearning, deepLearningLab])
  assert.equal(sgpa, 8.67)

  // Explicitly verify it does NOT average M1 marks directly as SGPA
  const rawAvgMarks = (deepLearning.predicted_end_sem_marks + deepLearningLab.predicted_end_sem_marks) / 2
  assert.notEqual(sgpa, rawAvgMarks) // 55.39 marks is not SGPA
  assert.notEqual(sgpa, (rawAvgMarks / 70) * 10) // 7.91 is naive linear scale
})

test("m1V3PredictedPercentage computes credit-weighted percentage", () => {
  // DL: 88.84% × 4 = 355.36
  // Lab: 76.00% × 2 = 152.00
  // Total = 507.36 / 6 = 84.56% -> 84.6%
  const pct = m1V3PredictedPercentage([deepLearning, deepLearningLab])
  assert.ok(pct !== null && Math.abs(pct - 84.6) <= 0.1)
})