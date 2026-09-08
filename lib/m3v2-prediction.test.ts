// Frontend tests for the M3 V2 at-risk card contract helpers.
//
// Runs with Node's built-in test runner + TypeScript type stripping:
//   node --experimental-test-module-mocks --test lib/m3v2-prediction.test.ts
//
// These helpers are pure-presentation mappings of the backend model output.
// Rules that must never regress:
//   - Feature names surfaced in `signals` are internal ML keys; the card must
//     show the human-readable label, never the raw key.
//   - A signal with a missing raw_value renders "Not available" (not "—", and
//     never a fabricated 0).
//   - Recovered/real signal values render with a sensible human format
//     (percentages as %, SGPA to 2dp, counts as integers).

import { test } from "node:test"
import assert from "node:assert/strict"

import {
  M3V2_FEATURE_LABELS,
  m3V2FeatureLabel,
  m3V2SignalValue,
  m3V2RiskTone,
} from "./m3v2-prediction.ts"
import type { M3V2Signal } from "./m3v2-prediction.ts"

function sig(overrides: Partial<M3V2Signal>): M3V2Signal {
  return { feature: "semester_sgpa", raw_value: 7.88, importance: 0.1, ...overrides }
}

test("every model feature key has a human-readable label", () => {
  const keys = [
    "semester_sgpa", "semester_percentage", "semester_total_marks",
    "semester_attendance_percentage", "backlog_count", "cumulative_backlog_events",
    "credits_registered", "credits_earned", "subjects_registered",
    "previous_sem_sgpa", "sgpa_drift", "sgpa_rolling_mean_3",
    "previous_sem_backlog_count", "backlog_change", "attendance_aggregate_pct",
    "subj_internal_marks_mean", "subj_internal_marks_std",
    "subj_mid_sem_marks_mean", "subj_end_sem_marks_mean", "subj_end_sem_marks_std",
    "subj_assignment_score_mean", "subj_quiz_avg_marks_mean",
    "subj_submission_delay_mean", "subj_pre_endsem_pct_mean",
    "subj_failed_subjects_count",
    "att_tsem_total_pct", "att_tsem_low_pct_weeks", "att_tsem_velocity_mean",
    "learn_tsem_volume_total", "learn_tsem_engagement_mean",
    "learn_tsem_completion_mean", "learn_tsem_late_mean",
    "is_male", "semester_no", "stress_ordinal", "study_hours_per_week",
  ]
  for (const k of keys) {
    const label = M3V2_FEATURE_LABELS[k]
    assert.ok(label && label.length > 0, `missing label for ${k}`)
    assert.ok(label !== k, `label for ${k} must differ from the raw key`)
    assert.equal(m3V2FeatureLabel(k), label)
  }
})

test("unknown feature keys fall back to the raw key", () => {
  assert.equal(m3V2FeatureLabel("some_future_feature"), "some_future_feature")
})

test("missing raw_value renders as 'Not available', never a zero", () => {
  for (const raw of [null, undefined]) {
    assert.equal(m3V2SignalValue(sig({ raw_value: raw })), "Not available")
  }
})

test("percent features render as percentages with 2-decimal parity", () => {
  assert.equal(m3V2SignalValue(sig({ feature: "attendance_aggregate_pct", raw_value: 87.35 })), "87.35%")
  assert.equal(m3V2SignalValue(sig({ feature: "semester_percentage", raw_value: 72.95 })), "72.95%")
  assert.equal(m3V2SignalValue(sig({ feature: "att_tsem_total_pct", raw_value: 0 })), "0.00%")
})

test("SGPA features keep 2-decimal precision", () => {
  assert.equal(m3V2SignalValue(sig({ feature: "sgpa_rolling_mean_3", raw_value: 7.88 })), "7.88")
  assert.equal(m3V2SignalValue(sig({ feature: "sgpa_drift", raw_value: -0.27 })), "-0.27")
})

test("count features render as integers", () => {
  assert.equal(m3V2SignalValue(sig({ feature: "subj_failed_subjects_count", raw_value: 2 })), "2")
  assert.equal(m3V2SignalValue(sig({ feature: "backlog_count", raw_value: 0 })), "0")
})

test("generic features fall back to 2-decimal formatting", () => {
  assert.equal(m3V2SignalValue(sig({ feature: "subj_submission_delay_mean", raw_value: 3.456 })), "3.46")
})

test("risk tone bounds stay monotonic", () => {
  assert.equal(m3V2RiskTone(null), "secondary")
  assert.equal(m3V2RiskTone(0.1), "success")
  assert.equal(m3V2RiskTone(0.2), "secondary")
  assert.equal(m3V2RiskTone(0.4), "warning")
  assert.equal(m3V2RiskTone(0.6), "destructive")
})