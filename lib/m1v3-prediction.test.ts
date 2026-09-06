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
  m1V3GradeTone,
  m1V3PredictedEndSem,
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
    attendance_percentage: 83.33,
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
    attendance_percentage: 88,
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