// Frontend tests for the pure student marks-simulation library.
//
// Runs with Node's built-in test runner + TypeScript type stripping
// (no extra dependencies):  node --test lib/student/marks-simulation.test.ts
//
// Covers the hard input-validation contract:
//   * per-field valid/invalid boundaries (Internal 0-20, Mid-Sem 0-50,
//     End-Sem 0-70)
//   * keyboard-hostile values (negative, scientific notation, NaN, Infinity,
//     decimals, whitespace) can never produce a derived result
//   * the exact repro: Internal=-25, Mid-Sem=90, End-Sem=-2 must NOT calculate
//   * End-Sem 0-17 is a valid input but can never be Pass
//   * incomplete input stays incomplete (nothing derived)

import { test } from "node:test"
import assert from "node:assert/strict"

import {
  MARKS_END_SEM_PASS_MIN,
  MARKS_END_SEM_MAX,
  MARKS_INTERNAL_MAX,
  MARKS_MID_SEM_MAX,
  parseMarksField,
  simulateMarks,
  type MarksComponentKey,
} from "./marks-simulation.ts"

function expectValid(field: MarksComponentKey, raw: string) {
  const parsed = parseMarksField(raw, field)
  assert.equal(parsed.valid, true, `expected ${raw} to be valid for ${field}`)
  assert.equal(parsed.error, null)
  return parsed.value
}

function expectInvalid(field: MarksComponentKey, raw: string) {
  const parsed = parseMarksField(raw, field)
  assert.equal(parsed.valid, false, `expected ${raw} to be invalid for ${field}`)
  assert.equal(parsed.value, null)
  assert.ok(parsed.error, `expected an error message for ${raw}`)
  return parsed.error
}

// ---------------------------------------------------------------------------
// parseMarksField — internal (0-20)
// ---------------------------------------------------------------------------
test("internal: 0 valid, 20 valid, 21 invalid, -1 invalid", () => {
  assert.equal(expectValid("internal_marks", "0"), 0)
  assert.equal(expectValid("internal_marks", "20"), 20)
  expectInvalid("internal_marks", "21")
  expectInvalid("internal_marks", "-1")
})

test("internal: whitespace-only is empty/incomplete, not invalid", () => {
  const parsed = parseMarksField("   ", "internal_marks")
  assert.equal(parsed.valid, true)
  assert.equal(parsed.value, null)
  assert.equal(parsed.error, null)
})

// ---------------------------------------------------------------------------
// parseMarksField — mid-sem (0-50)
// ---------------------------------------------------------------------------
test("mid: 0 valid, 50 valid, 51 invalid, -1 invalid", () => {
  assert.equal(expectValid("mid_sem_marks", "0"), 0)
  assert.equal(expectValid("mid_sem_marks", "50"), 50)
  expectInvalid("mid_sem_marks", "51")
  expectInvalid("mid_sem_marks", "-1")
})

// ---------------------------------------------------------------------------
// parseMarksField — end-sem (0-70)
// ---------------------------------------------------------------------------
test("end: 0 valid, 70 valid, 71 invalid, -1 invalid", () => {
  assert.equal(expectValid("end_sem_marks", "0"), 0)
  assert.equal(expectValid("end_sem_marks", "70"), 70)
  expectInvalid("end_sem_marks", "71")
  expectInvalid("end_sem_marks", "-1")
})

// ---------------------------------------------------------------------------
// Keyboard-hostile values (parse level)
// ---------------------------------------------------------------------------
test("parse: scientific notation, signs, decimals and garbage are rejected", () => {
  for (const raw of ["1e5", "1E5", "+5", "5.", ".5", "12.5", "12,5", "5 0", "abc", "--", "Infinity", "-Infinity", "NaN"]) {
    expectInvalid("mid_sem_marks", raw)
  }
})

// ---------------------------------------------------------------------------
// simulateMarks — hard validation of numeric inputs (defense in depth)
// ---------------------------------------------------------------------------
test("simulate: invalid repro (-25, 90, -2) never calculates", () => {
  const result = simulateMarks({ internal_marks: -25, mid_sem_marks: 90, end_sem_marks: -2 })
  assert.equal(result.status, "invalid")
  assert.equal(result.complete, false)
  assert.equal(result.errors.internal_marks, "Internal marks must be between 0 and 20.")
  assert.equal(result.errors.mid_sem_marks, "Mid-Sem marks must be between 0 and 50.")
  assert.equal(result.errors.end_sem_marks, "End-Sem marks must be between 0 and 70.")
  assert.equal(result.total_marks, null)
  assert.equal(result.percentage, null)
  assert.equal(result.grade, null)
  assert.equal(result.result_status, null)
})

test("simulate: single over-max field is invalid and derives nothing", () => {
  const result = simulateMarks({ internal_marks: 20, mid_sem_marks: 90, end_sem_marks: 70 })
  assert.equal(result.status, "invalid")
  assert.equal(result.total_marks, null)
  assert.equal(result.percentage, null)
})

test("simulate: negative internal is invalid and derives nothing", () => {
  const result = simulateMarks({ internal_marks: -25, mid_sem_marks: 50, end_sem_marks: 70 })
  assert.equal(result.status, "invalid")
  assert.equal(result.total_marks, null)
})

test("simulate: NaN, Infinity and -Infinity are invalid", () => {
  for (const bad of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
    const result = simulateMarks({ internal_marks: 20, mid_sem_marks: 50, end_sem_marks: bad })
    assert.equal(result.status, "invalid", `end_sem_marks=${bad} must be invalid`)
    assert.equal(result.total_marks, null)
  }
})

test("simulate: decimal marks are invalid", () => {
  const result = simulateMarks({ internal_marks: 20, mid_sem_marks: 49.5, end_sem_marks: 60 })
  assert.equal(result.status, "invalid")
  assert.equal(result.total_marks, null)
})

test("simulate: empty/incomplete input stays incomplete and derives nothing", () => {
  const partial = simulateMarks({ internal_marks: 20, mid_sem_marks: 50, end_sem_marks: null })
  assert.equal(partial.status, "incomplete")
  assert.equal(partial.complete, false)
  assert.equal(partial.total_marks, null)
  assert.equal(partial.percentage, null)
  assert.equal(partial.end_sem_min_warning, false, "no min-18 warning when end-sem not entered")

  const empty = simulateMarks({ internal_marks: null, mid_sem_marks: null, end_sem_marks: null })
  assert.equal(empty.status, "incomplete")
  assert.equal(empty.total_marks, null)
})

// ---------------------------------------------------------------------------
// End-Sem pass minimum
// ---------------------------------------------------------------------------
test(`simulate: end-sem ${MARKS_END_SEM_PASS_MIN - 1} cannot pass even with high total`, () => {
  const result = simulateMarks({ internal_marks: 20, mid_sem_marks: 50, end_sem_marks: 17 })
  assert.equal(result.status, "complete")
  assert.equal(result.total_marks, 87)
  assert.equal(result.percentage, 62.14)
  assert.equal(result.grade, "B+")
  assert.equal(result.result_status, "Fail")
  assert.equal(result.end_sem_min_warning, true)
})

test("simulate: end-sem 0 is valid input but cannot pass", () => {
  const result = simulateMarks({ internal_marks: 20, mid_sem_marks: 50, end_sem_marks: 0 })
  assert.equal(result.status, "complete")
  assert.equal(result.percentage, 50)
  assert.equal(result.result_status, "Fail")
  assert.equal(result.end_sem_min_warning, true)
})

test(`simulate: end-sem ${MARKS_END_SEM_PASS_MIN} is eligible for pass`, () => {
  const result = simulateMarks({ internal_marks: 20, mid_sem_marks: 50, end_sem_marks: 18 })
  assert.equal(result.status, "complete")
  assert.equal(result.total_marks, 88)
  assert.equal(result.percentage, 62.86)
  assert.equal(result.result_status, "Pass")
  assert.equal(result.end_sem_min_warning, false)
})

test(`simulate: end-sem ${MARKS_END_SEM_MAX} is valid and passes`, () => {
  const result = simulateMarks({ internal_marks: 0, mid_sem_marks: 0, end_sem_marks: 70 })
  assert.equal(result.status, "complete")
  assert.equal(result.total_marks, 70)
  assert.equal(result.percentage, 50)
  assert.equal(result.result_status, "Pass")
})

// ---------------------------------------------------------------------------
// Canonical derivation regression
// ---------------------------------------------------------------------------
test("simulate: 18, 49, 60 -> total 127, percentage 90.71, canonical result", () => {
  const result = simulateMarks({ internal_marks: 18, mid_sem_marks: 49, end_sem_marks: 60 })
  assert.equal(result.status, "complete")
  assert.equal(result.total_marks, 127)
  assert.equal(result.percentage, 90.71)
  assert.equal(result.grade, "O")
  assert.equal(result.grade_point, 10)
  assert.equal(result.result_status, "Pass")
  assert.equal(result.performance_category, "Top")
  assert.equal(result.remarks, "Excellent performance")
})

test("simulate: 20, 50, 70 -> total 140, percentage 100", () => {
  const result = simulateMarks({ internal_marks: 20, mid_sem_marks: 50, end_sem_marks: 70 })
  assert.equal(result.status, "complete")
  assert.equal(result.total_marks, 140)
  assert.equal(result.percentage, 100)
  assert.equal(result.result_status, "Pass")
})

// ---------------------------------------------------------------------------
// Maxima mirrors (guard against drift)
// ---------------------------------------------------------------------------
test("constants match the canonical scheme", () => {
  assert.equal(MARKS_INTERNAL_MAX, 20)
  assert.equal(MARKS_MID_SEM_MAX, 50)
  assert.equal(MARKS_END_SEM_MAX, 70)
  assert.equal(MARKS_END_SEM_PASS_MIN, 18)
})
