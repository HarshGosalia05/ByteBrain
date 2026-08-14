// Frontend tests for the pure student attendance-simulation library.
//
// Runs with Node's built-in test runner + TypeScript type stripping
// (no extra dependencies):  node --test lib/student/attendance-simulation.test.ts
//
// Covers the hard input-validation contract:
//   * per-field valid/invalid boundaries (Attend/Miss next 0-100)
//   * keyboard-hostile values (negative, scientific notation, NaN, Infinity,
//     decimals, signs, whitespace, symbols) can never produce a derived result
//   * the exact repros: -200000, 12333333333333333333, 1.5, 1e10 must NOT calculate
//   * empty or whitespace-only inputs default safely to 0
//   * valid integers (0, 5, 20, 100) compute correct projections
//   * simulation remains strictly hypothetical and deterministic

import { test } from "node:test"
import assert from "node:assert/strict"

import {
  ATTENDANCE_SIMULATION_MAX_CLASSES,
  ATTENDANCE_SIMULATION_MIN_CLASSES,
  parseAttendanceField,
  simulateAttendance,
  type AttendanceSimulationFieldKey,
} from "./attendance-simulation.ts"

function expectValid(field: AttendanceSimulationFieldKey, raw: string) {
  const parsed = parseAttendanceField(raw, field)
  assert.equal(parsed.valid, true, `expected "${raw}" to be valid for ${field}`)
  assert.equal(parsed.error, null)
  return parsed.value
}

function expectInvalid(field: AttendanceSimulationFieldKey, raw: string) {
  const parsed = parseAttendanceField(raw, field)
  assert.equal(parsed.valid, false, `expected "${raw}" to be invalid for ${field}`)
  assert.equal(parsed.value, null)
  assert.ok(parsed.error, `expected an error message for "${raw}"`)
  return parsed.error
}

// ---------------------------------------------------------------------------
// parseAttendanceField — Valid boundaries (0 to 100)
// ---------------------------------------------------------------------------
test("attendance field: 0 valid, 100 valid, 101 invalid, -1 invalid", () => {
  assert.equal(expectValid("present", "0"), 0)
  assert.equal(expectValid("present", "1"), 1)
  assert.equal(expectValid("present", "50"), 50)
  assert.equal(expectValid("present", "100"), 100)
  expectInvalid("present", "101")
  expectInvalid("present", "-1")

  assert.equal(expectValid("absent", "0"), 0)
  assert.equal(expectValid("absent", "100"), 100)
  expectInvalid("absent", "101")
  expectInvalid("absent", "-1")
})

test("attendance field: empty or whitespace-only is valid default 0", () => {
  const empty = parseAttendanceField("", "present")
  assert.equal(empty.valid, true)
  assert.equal(empty.value, 0)
  assert.equal(empty.error, null)

  const spaces = parseAttendanceField("   ", "absent")
  assert.equal(spaces.valid, true)
  assert.equal(spaces.value, 0)
  assert.equal(spaces.error, null)
})

// ---------------------------------------------------------------------------
// parseAttendanceField — Specific forbidden inputs from problem report
// ---------------------------------------------------------------------------
test("attendance field: negative repro (-200000) is rejected", () => {
  expectInvalid("present", "-200000")
  expectInvalid("absent", "-200000")
})

test("attendance field: huge number repro (12333333333333333333) is rejected", () => {
  expectInvalid("present", "12333333333333333333")
  expectInvalid("absent", "12333333333333333333")
})

test("attendance field: decimal repro (1.5) is rejected", () => {
  expectInvalid("present", "1.5")
  expectInvalid("absent", "1.5")
})

test("attendance field: scientific notation repro (1e10, 1E5) is rejected", () => {
  expectInvalid("present", "1e10")
  expectInvalid("present", "1E5")
  expectInvalid("absent", "1e10")
  expectInvalid("absent", "1E5")
})

test("attendance field: non-numeric, signs and symbols are rejected", () => {
  const badInputs = [
    "+5",
    "5.",
    ".5",
    "0.0",
    "12,5",
    "5 0",
    "abc",
    "--",
    "Infinity",
    "-Infinity",
    "NaN",
    "null",
    "undefined",
  ]
  for (const raw of badInputs) {
    expectInvalid("present", raw)
    expectInvalid("absent", raw)
  }
})

// ---------------------------------------------------------------------------
// simulateAttendance — Hard validation of numeric inputs (defense-in-depth)
// ---------------------------------------------------------------------------
test("simulate: invalid negative or huge numbers never calculate", () => {
  const resultNegative = simulateAttendance({
    total_classes: 40,
    attended_classes: 32,
    hypothetical_present: -200000,
    hypothetical_absent: 0,
  })
  assert.equal(resultNegative.complete, false)
  assert.equal(resultNegative.resulting_attendance, null)
  assert.equal(resultNegative.delta, null)

  const resultHuge = simulateAttendance({
    total_classes: 40,
    attended_classes: 32,
    hypothetical_present: 500,
    hypothetical_absent: 0,
  })
  assert.equal(resultHuge.complete, false)
  assert.equal(resultHuge.resulting_attendance, null)
  assert.equal(resultHuge.delta, null)

  const resultDecimal = simulateAttendance({
    total_classes: 40,
    attended_classes: 32,
    hypothetical_present: 1.5,
    hypothetical_absent: 0,
  })
  assert.equal(resultDecimal.complete, false)
  assert.equal(resultDecimal.resulting_attendance, null)
  assert.equal(resultDecimal.delta, null)

  const resultNull = simulateAttendance({
    total_classes: 40,
    attended_classes: 32,
    hypothetical_present: null,
    hypothetical_absent: 0,
  })
  assert.equal(resultNull.complete, false)
  assert.equal(resultNull.resulting_attendance, null)
  assert.equal(resultNull.delta, null)
})

// ---------------------------------------------------------------------------
// simulateAttendance — Valid calculation scenarios
// ---------------------------------------------------------------------------
test("simulate: valid inputs compute projected attendance correctly", () => {
  // Baseline: 40 classes total, 32 attended (80.0%)
  // Attend next 2 classes: 34 / 42 = 80.95% (+0.95%)
  const resultAttend = simulateAttendance({
    total_classes: 40,
    attended_classes: 32,
    hypothetical_present: 2,
    hypothetical_absent: 0,
    target_attendance: 75,
  })
  assert.equal(resultAttend.complete, true)
  assert.equal(resultAttend.current_attendance, 80)
  assert.equal(resultAttend.resulting_attendance, 80.95)
  assert.equal(resultAttend.delta, 0.95)
  assert.equal(resultAttend.at_target, true)
  assert.equal(resultAttend.attendance_status, "Good")
  assert.equal(resultAttend.eligibility_status, "Eligible")
  assert.equal(resultAttend.shortage_flag, "No")

  // Miss next 4 classes: 32 / 44 = 72.73% (-7.27%)
  const resultMiss = simulateAttendance({
    total_classes: 40,
    attended_classes: 32,
    hypothetical_present: 0,
    hypothetical_absent: 4,
    target_attendance: 75,
  })
  assert.equal(resultMiss.complete, true)
  assert.equal(resultMiss.current_attendance, 80)
  assert.equal(resultMiss.resulting_attendance, 72.73)
  assert.equal(resultMiss.delta, -7.27)
  assert.equal(resultMiss.at_target, false)
  assert.equal(resultMiss.attendance_status, "Low")
  assert.equal(resultMiss.eligibility_status, "Not Eligible")
  assert.equal(resultMiss.shortage_flag, "Yes")
})

test("simulate: missing baseline remains incomplete", () => {
  const result = simulateAttendance({
    total_classes: null,
    attended_classes: null,
    hypothetical_present: 5,
    hypothetical_absent: 0,
  })
  assert.equal(result.complete, false)
  assert.equal(result.resulting_attendance, null)
  assert.equal(result.delta, null)
})
