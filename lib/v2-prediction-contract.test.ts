// Frontend tests for the M1/M2/M3 V2 prediction-contract helper functions.
//
// Runs with Node's built-in test runner + TypeScript type stripping:
//   node --experimental-test-module-mocks --test lib/v2-prediction-contract.test.ts
//
// These helpers are pure-presentation mappings of the backend model output.
// They must never introduce a confidence value, a causal claim, or a guarantee —
// they only turn an existing model value into a badge tone / risk label.

import { test } from "node:test"
import assert from "node:assert/strict"

import { m1V2GradeTone } from "./m1v2-prediction.ts"
import { m2V2SgpaTone } from "./m2v2-prediction.ts"
import { m3V2RiskTone, riskLevelLabel, formatRiskPercent } from "./m3v2-prediction.ts"

// ---------------------------------------------------------------------------
// M1 V2 grade tone (maps the backend grade band letters to a badge variant)
// ---------------------------------------------------------------------------

test("m1V2GradeTone maps top bands to success", () => {
  assert.equal(m1V2GradeTone("O"), "success")
  assert.equal(m1V2GradeTone("A+"), "success")
  assert.equal(m1V2GradeTone("A"), "success")
  assert.equal(m1V2GradeTone("B+"), "success")
})

test("m1V2GradeTone maps average band to secondary", () => {
  assert.equal(m1V2GradeTone("B"), "secondary")
})

test("m1V2GradeTone maps borderline pass to warning", () => {
  assert.equal(m1V2GradeTone("C"), "warning")
})

test("m1V2GradeTone maps failing band to destructive", () => {
  assert.equal(m1V2GradeTone("F"), "destructive")
})

test("m1V2GradeTone is case/whitespace insensitive", () => {
  assert.equal(m1V2GradeTone("  a+ "), "success")
  assert.equal(m1V2GradeTone("f"), "destructive")
  assert.equal(m1V2GradeTone("c"), "warning")
})

// ---------------------------------------------------------------------------
// M2 V2 SGPA tone
// ---------------------------------------------------------------------------

test("m2V2SgpaTone returns secondary for null (no forecast)", () => {
  assert.equal(m2V2SgpaTone(null), "secondary")
})

test("m2V2SgpaTone maps SGPA bands to tone", () => {
  assert.equal(m2V2SgpaTone(8.0), "success")
  assert.equal(m2V2SgpaTone(7.0), "secondary")
  assert.equal(m2V2SgpaTone(6.0), "warning")
  assert.equal(m2V2SgpaTone(5.0), "destructive")
})

// ---------------------------------------------------------------------------
// M3 V2 risk tone and risk-level label
// ---------------------------------------------------------------------------

test("m3V2RiskTone maps null to secondary", () => {
  assert.equal(m3V2RiskTone(null), "secondary")
})

test("m3V2RiskTone maps probability to tone", () => {
  assert.equal(m3V2RiskTone(0.6), "destructive")
  assert.equal(m3V2RiskTone(0.4), "warning")
  assert.equal(m3V2RiskTone(0.2), "secondary")
  assert.equal(m3V2RiskTone(0.05), "success")
})

test("riskLevelLabel returns a categorized label, not a fabricated number", () => {
  assert.equal(riskLevelLabel(0.6), "High")
  assert.equal(riskLevelLabel(0.4), "Moderate")
  assert.equal(riskLevelLabel(0.2), "Low-moderate")
  assert.equal(riskLevelLabel(0.05), "Low")
  assert.equal(riskLevelLabel(null), "—")
})

// ---------------------------------------------------------------------------
// M3 V2 risk percent formatting (presentation-only)
// ---------------------------------------------------------------------------

test("formatRiskPercent formats probability as integer percent", () => {
  assert.equal(formatRiskPercent(0.571), "57%")
  assert.equal(formatRiskPercent(0.282), "28%")
  assert.equal(formatRiskPercent(null), "—")
})