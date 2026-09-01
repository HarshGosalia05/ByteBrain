import { test, mock, beforeEach } from "node:test"
import assert from "node:assert/strict"

import type { FacultyStudentMlInsights } from "./faculty-api.ts"

// ---------------------------------------------------------------------------
// Session mock. Registered BEFORE faculty-api is imported so that the real
// student-session.ts (which imports next/headers, not resolvable in plain
// Node) is never loaded.
// ---------------------------------------------------------------------------

let activeSession: unknown = null

mock.module("./student-session.ts", {
  namedExports: {
    getSessionUser: async () => activeSession,
  },
})

const facultyApi = await import("./faculty-api.ts")

// ---------------------------------------------------------------------------
// Fetch mock
// ---------------------------------------------------------------------------

const DEFAULT_SESSION = {
  user_id: "u-1",
  username: "fprof",
  role: "Faculty",
  department: "CSE",
  faculty_id: "FAC-A",
}

type FetchCall = { url: string; init?: RequestInit }

const calls: FetchCall[] = []
const routes = new Map<string, { status?: number; body?: unknown }>()
let defaultStatus = 200
let defaultBody: unknown = {}

function route(substring: string, status: number, body: unknown) {
  routes.set(substring, { status, body })
}

function installFetchMock() {
  globalThis.fetch = (async (url: unknown, init?: RequestInit) => {
    const urlString = String(url)
    calls.push({ url: urlString, init })
    const hit = [...routes.keys()].find((key) => urlString.includes(key))
    const status = hit ? (routes.get(hit)!.status ?? defaultStatus) : defaultStatus
    const body = hit ? routes.get(hit)!.body : defaultBody
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    } as Response
  }) as typeof fetch
}

beforeEach(() => {
  activeSession = DEFAULT_SESSION
  calls.length = 0
  routes.clear()
  defaultStatus = 200
  defaultBody = {}
  ;(globalThis as { bffCache?: Map<unknown, unknown> }).bffCache?.clear()
  installFetchMock()
})

function getCalls(substring: string): FetchCall[] {
  return calls.filter((c) => c.url.includes(substring))
}

const ML_INSIGHTS_BODY: FacultyStudentMlInsights = {
  student_id: "STU-A",
  generated_at: "2026-08-13T06:00:00+00:00",
  models: {
    m1: {
      available: true,
      prediction: {
        model_id: "m1",
        predictions: [
          {
            student_id: "STU-A",
            subject_id: "SUB001",
            semester_no: 3,
            predicted_end_sem_marks: 55.5,
            clipped: false,
          },
        ],
        input_row_count: 1,
        prediction_count: 1,
      },
      explanation: {
        model_id: "m1",
        prediction_type: "m1",
        student_id: "STU-A",
        explanation_kind: "grounded_rule_based",
        model_metadata: {
          model_id: "m1",
          model_type: "supervised",
          algorithm: "linear",
          task: "regression",
          target: "end_sem_marks",
        },
        model_version: "1",
        not_supported: ["confidence", "probability", "feature_importance"],
        rule_context: {},
        explanations: [
          {
            prediction_type: "m1",
            subject_id: "SUB001",
            subject_name: null,
            semester_no: 3,
            predicted_end_sem_marks: 55.5,
            clipped: false,
            projected_percentage: null,
            projected_band: null,
            inputs: [{ name: "internal_marks", value: 14.5, present: true }],
            factors: [],
            interpretation: "M1 predicts end-semester marks of 55.5 for SUB001.",
          },
        ],
      },
    },
    m2: {
      available: true,
      prediction: {
        model_id: "m2",
        predictions: [
          {
            student_id: "STU-A",
            semester_no: 4,
            predicted_next_semester_sgpa: 7.4,
            predicted_next_semester_percentage: 66.5,
          },
        ],
        input_row_count: 1,
        prediction_count: 1,
      },
      explanation: {
        model_id: "m2",
        prediction_type: "m2",
        student_id: "STU-A",
        explanation_kind: "grounded_rule_based",
        model_metadata: {
          model_id: "m2",
          model_type: "supervised",
          algorithm: "linear",
          task: "regression",
          target: "sgpa",
        },
        model_version: "1",
        not_supported: ["confidence", "probability", "feature_importance"],
        rule_context: {},
        explanations: [
          {
            prediction_type: "m2",
            semester_no: 4,
            predicted_next_semester_sgpa: 7.4,
            predicted_next_semester_percentage: 66.5,
            current_percentage: null,
            projected_delta_percentage: null,
            inputs: [],
            factors: [],
            interpretation: "M2 predicts a next-semester SGPA of 7.4.",
          },
        ],
      },
    },
    m3: {
      available: false,
      reason: "no_data",
      message: "No data found for student STU-A",
    },
    m4: {
      available: true,
      prediction: {
        model_id: "m4",
        predictions: [
          {
            student_id: "STU-A",
            enrollment_no: "2023010001",
            full_name: "Alice",
            department_name: "Computer Science",
            current_semester: 3,
            career_readiness_score: 62.0,
            career_readiness_level: "Medium",
            positive_factors: "Strong academic standing",
            risk_factors: "Low internship exposure",
          },
        ],
        input_row_count: 1,
        prediction_count: 1,
      },
      explanation: {
        model_id: "m4",
        prediction_type: "m4",
        student_id: "STU-A",
        explanation_kind: "grounded_rule_based",
        model_metadata: {
          model_id: "m4",
          model_type: "deterministic",
          algorithm: "rule_based",
          task: "scoring",
          target: "career_readiness",
        },
        model_version: "1",
        not_supported: ["confidence", "probability", "feature_importance"],
        rule_context: {},
        explanations: [
          {
            prediction_type: "m4",
            readiness_score: 62.0,
            readiness_level: "Medium",
            positive_factors: ["Strong academic standing"],
            risk_factors: ["Low internship exposure"],
            inputs: [],
            interpretation: "M4 computes a rule-based career-readiness score of 62.0/100.",
          },
        ],
      },
    },
  },
}

// ---------------------------------------------------------------------------
// getFacultyStudentMlInsights
// ---------------------------------------------------------------------------

test("getFacultyStudentMlInsights fetches the faculty insights endpoint with auth", async () => {
  route("/students/STU-A/ml-insights", 200, ML_INSIGHTS_BODY)

  const result = await facultyApi.getFacultyStudentMlInsights("STU-A")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.student_id, "STU-A")
  assert.deepEqual(Object.keys(result.data.models), ["m1", "m2", "m3", "m4"])
  assert.equal(result.data.models.m3.available, false)
  assert.equal(result.data.models.m3.reason, "no_data")

  const hit = getCalls("/students/STU-A/ml-insights")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/faculty/students/STU-A/ml-insights")
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("getFacultyStudentMlInsights preserves NULL fields (never coerced to zero)", async () => {
  route("/students/STU-A/ml-insights", 200, ML_INSIGHTS_BODY)

  const result = await facultyApi.getFacultyStudentMlInsights("STU-A")
  assert.equal(result.ok, true)
  if (!result.ok) return
  const m1 = result.data.models.m1
  const m2 = result.data.models.m2
  assert.equal(m1.available, true)
  if (m1.available) {
    const explanations = m1.explanation.explanations as Array<{
      projected_percentage: number | null
      projected_band: string | null
      subject_name: string | null
    }>
    assert.equal(explanations[0].projected_percentage, null)
    assert.equal(explanations[0].projected_band, null)
    assert.equal(explanations[0].subject_name, null)
  }
  assert.equal(m2.available, true)
  if (m2.available) {
    const explanations = m2.explanation.explanations as Array<{
      current_percentage: number | null
      projected_delta_percentage: number | null
    }>
    assert.equal(explanations[0].current_percentage, null)
    assert.equal(explanations[0].projected_delta_percentage, null)
  }
})

test("getFacultyStudentMlInsights URL-encodes the student id", async () => {
  route("/ml-insights", 200, ML_INSIGHTS_BODY)

  const result = await facultyApi.getFacultyStudentMlInsights("STU A/1")
  assert.equal(result.ok, true)
  const hit = getCalls("/ml-insights")
  assert.equal(hit.length, 1)
  assert.ok(hit[0].url.endsWith("/students/STU%20A%2F1/ml-insights"))
})

test("getFacultyStudentMlInsights caches per faculty+student within TTL", async () => {
  route("/students/STU-A/ml-insights", 200, ML_INSIGHTS_BODY)

  const first = await facultyApi.getFacultyStudentMlInsights("STU-A")
  const second = await facultyApi.getFacultyStudentMlInsights("STU-A")
  assert.equal(first.ok, true)
  assert.equal(second.ok, true)
  assert.equal(getCalls("/students/STU-A/ml-insights").length, 1)
})

test("getFacultyStudentMlInsights maps 404 to not_found", async () => {
  route("/ml-insights", 404, { detail: "Student not found in your classes or mentees" })

  const result = await facultyApi.getFacultyStudentMlInsights("STU-MISSING")
  assert.equal(result.ok, false)
  if (result.ok) return
  assert.equal(result.error.code, "not_found")
})

test("getFacultyStudentMlInsights requires a session", async () => {
  activeSession = null

  const result = await facultyApi.getFacultyStudentMlInsights("STU-A")
  assert.equal(result.ok, false)
  if (result.ok) return
  assert.equal(result.error.status, 401)
  assert.equal(getCalls("/ml-insights").length, 0)
})

test("getFacultyStudentMlInsights rejects non-faculty roles", async () => {
  activeSession = { ...DEFAULT_SESSION, role: "Student", student_id: "STU-A" }

  const result = await facultyApi.getFacultyStudentMlInsights("STU-A")
  assert.equal(result.ok, false)
  if (result.ok) return
  assert.equal(result.error.status, 403)
  assert.equal(getCalls("/ml-insights").length, 0)
})

test("getFacultyStudentMlInsights rejects accounts without a faculty link", async () => {
  activeSession = { ...DEFAULT_SESSION, faculty_id: null }

  const result = await facultyApi.getFacultyStudentMlInsights("STU-A")
  assert.equal(result.ok, false)
  if (result.ok) return
  assert.equal(result.error.status, 400)
  assert.equal(result.error.code, "unlinked")
  assert.equal(getCalls("/ml-insights").length, 0)
})

// ---------------------------------------------------------------------------
// ML rendering helpers
// ---------------------------------------------------------------------------

test("facultyMlAvailableCount counts available models only", () => {
  assert.equal(facultyApi.facultyMlAvailableCount(ML_INSIGHTS_BODY.models), 3)
  assert.equal(
    facultyApi.facultyMlAvailableCount({
      m1: { available: false, reason: "no_data", message: "x" },
      m2: { available: false, reason: "error", message: "x" },
      m3: { available: false, reason: "no_data", message: "x" },
      m4: { available: false, reason: "error", message: "x" },
    }),
    0,
  )
})

test("facultyMlBandTone maps documented bands to tones", () => {
  assert.equal(facultyApi.facultyMlBandTone("Top Performer"), "success")
  assert.equal(facultyApi.facultyMlBandTone("Above Average"), "success")
  assert.equal(facultyApi.facultyMlBandTone("Average"), "secondary")
  assert.equal(facultyApi.facultyMlBandTone("Below Average"), "warning")
  assert.equal(facultyApi.facultyMlBandTone("Unknown"), "destructive")
  assert.equal(facultyApi.facultyMlBandTone(null), "destructive")
  assert.equal(facultyApi.facultyMlBandTone(undefined), "destructive")
})

test("facultyMlReadinessTone maps readiness levels to tones", () => {
  assert.equal(facultyApi.facultyMlReadinessTone("High"), "success")
  assert.equal(facultyApi.facultyMlReadinessTone("high"), "success")
  assert.equal(facultyApi.facultyMlReadinessTone("Medium"), "warning")
  assert.equal(facultyApi.facultyMlReadinessTone("Low"), "destructive")
})

// ---------------------------------------------------------------------------
// ML-12 Faculty Feedback Loop — BFF layer
// ---------------------------------------------------------------------------

const FEEDBACK_CONTEXT_BODY = {
  student_id: "STU-A",
  latest_m3_prediction: {
    prediction_id: "pred-1",
    model_version: "3.2.1",
    generated_at: "2026-08-13T06:00:00+00:00",
    is_at_risk_next_sem: 1,
    risk_probability: 0.82,
  },
  current_verdict: null,
  feedback_history: [],
}

test("getStudentPredictionFeedbackContext fetches the feedback endpoint with auth", async () => {
  route("/students/STU-A/feedback", 200, FEEDBACK_CONTEXT_BODY)

  const result = await facultyApi.getStudentPredictionFeedbackContext("STU-A")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.student_id, "STU-A")
  assert.equal(result.data.latest_m3_prediction?.prediction_id, "pred-1")
  assert.equal(result.data.latest_m3_prediction?.is_at_risk_next_sem, 1)
  assert.equal(result.data.current_verdict, null)

  const hit = getCalls("/students/STU-A/feedback")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/faculty/students/STU-A/feedback")
})

test("getStudentPredictionFeedbackContext URL-encodes the student id", async () => {
  route("/students/STU%20A%2F1/feedback", 200, FEEDBACK_CONTEXT_BODY)

  const result = await facultyApi.getStudentPredictionFeedbackContext("STU A/1")
  assert.equal(result.ok, true)
  const hit = getCalls("/feedback")
  assert.equal(hit.length, 1)
  assert.ok(hit[0].url.endsWith("/students/STU%20A%2F1/feedback"))
})

test("getPredictionFeedback maps 404 to not_found", async () => {
  route("/predictions/pred-missing/feedback", 404, { detail: "Prediction not found" })

  const result = await facultyApi.getPredictionFeedback("pred-missing")
  assert.equal(result.ok, false)
  if (result.ok) return
  assert.equal(result.error.code, "not_found")
})

test("submitPredictionFeedback POSTs the review body with auth", async () => {
  route("/predictions/pred-1/feedback", 200, {
    feedback_id: "fb-1",
    prediction_id: "pred-1",
    student_id: "STU-A",
    faculty_id: "FAC-A",
    feedback_action: "confirmed",
    note: "solid prediction",
    model_version: "3.2.1",
    feedback_timestamp: "2026-08-13T06:00:00+00:00",
  })

  const result = await facultyApi.submitPredictionFeedback(
    "pred-1",
    { action: "confirmed", note: "solid prediction" },
    "STU-A",
  )
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.feedback_action, "confirmed")

  const hit = getCalls("/predictions/pred-1/feedback")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].init?.method, "POST")
  const body = JSON.parse(String(hit[0].init?.body))
  assert.deepEqual(body, { action: "confirmed", note: "solid prediction" })
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("submitPredictionFeedback sends null note (never an empty string)", async () => {
  route("/predictions/pred-1/feedback", 200, { feedback_id: "fb-2" })

  const result = await facultyApi.submitPredictionFeedback(
    "pred-1",
    { action: "dismissed", note: "" },
    "STU-A",
  )
  assert.equal(result.ok, true)
  const hit = getCalls("/feedback")
  const body = JSON.parse(String(hit[0].init?.body))
  assert.equal(body.action, "dismissed")
  assert.equal(body.note, null)
})

test("submitPredictionFeedback invalidates the cached feedback context", async () => {
  route("/students/STU-A/feedback", 200, FEEDBACK_CONTEXT_BODY)
  route("/predictions/pred-1/feedback", 200, { feedback_id: "fb-3" })

  // Prime the feedback-context cache.
  const first = await facultyApi.getStudentPredictionFeedbackContext("STU-A")
  assert.equal(first.ok, true)
  assert.equal(getCalls("/students/STU-A/feedback").length, 1)

  // Submit a review -> must invalidate that context cache.
  const submit = await facultyApi.submitPredictionFeedback(
    "pred-1",
    { action: "confirmed" },
    "STU-A",
  )
  assert.equal(submit.ok, true)

  const second = await facultyApi.getStudentPredictionFeedbackContext("STU-A")
  assert.equal(second.ok, true)
  assert.equal(
    getCalls("/students/STU-A/feedback").length,
    2,
    "feedback context must be re-fetched after a submit",
  )
})

test("submitPredictionFeedback requires a session", async () => {
  activeSession = null

  const result = await facultyApi.submitPredictionFeedback(
    "pred-1",
    { action: "confirmed" },
    "STU-A",
  )
  assert.equal(result.ok, false)
  if (result.ok) return
  assert.equal(result.error.status, 401)
  assert.equal(getCalls("/feedback").length, 0)
})

// ---------------------------------------------------------------------------
// getFacultyStudentM1V2 — M1 V2 Subject Marks Prediction
// Hits the generic /predict/m1v2/{student_id} route (NOT under /faculty/) with
// the Faculty bearer token. Server-side authorize_prediction_access enforces
// faculty scope (incl. mentees under the mentorship relationship).
// ---------------------------------------------------------------------------

const M1V2_FACULTY_BODY = {
  student_id: "STU-A",
  model_id: "m1_v2",
  model_version: "2.0",
  algorithm: "ridge",
  readiness_status: "READY",
  reason: null,
  current_semester: 3,
  prediction_count: 1,
  predicted_at: "2026-09-01T08:00:00Z",
  inference_ms: 3.2,
  subjects: [
    {
      subject_id: "SUB001",
      semester_no: 3,
      predicted_end_sem_marks: 45.2,
      target_max: 70,
      grade_band: "Below Average",
      grade_label: "C+",
      input_features: {
        internal_marks: 14.0,
        mid_sem_marks: 11.0,
        att_total_pct: 71.0,
        pre_endsem_assessment_pct: 42.0,
      },
    },
  ],
  note: "Predicted end-sem marks are model estimates, not actual results.",
}

test("getFacultyStudentM1V2 hits the generic predict route with faculty auth", async () => {
  route("/predict/m1v2/STU-A", 200, M1V2_FACULTY_BODY)

  const result = await facultyApi.getFacultyStudentM1V2("STU-A")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.model_id, "m1_v2")
  assert.equal(result.data.model_version, "2.0")
  assert.equal(result.data.readiness_status, "READY")
  assert.equal(result.data.subjects[0].grade_band, "Below Average")

  const hit = getCalls("/predict/m1v2")
  assert.equal(hit.length, 1)
  // M1 V2 lives outside /faculty/ — verify the exact generic route.
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m1v2/STU-A")
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("getFacultyStudentM1V2 URL-encodes the student id", async () => {
  route("/predict/m1v2/STU%20A%2F1", 200, M1V2_FACULTY_BODY)

  const result = await facultyApi.getFacultyStudentM1V2("STU A/1")
  assert.equal(result.ok, true)
  const hit = getCalls("/predict/m1v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m1v2/STU%20A%2F1")
})

test("getFacultyStudentM1V2 caches per faculty+student within TTL", async () => {
  route("/predict/m1v2/STU-A", 200, M1V2_FACULTY_BODY)

  await facultyApi.getFacultyStudentM1V2("STU-A")
  await facultyApi.getFacultyStudentM1V2("STU-A")
  assert.equal(getCalls("/predict/m1v2").length, 1)
})

test("getFacultyStudentM1V2 returns 200 with NO_DATA for unavailable predictions", async () => {
  const NO_DATA_BODY = {
    ...M1V2_FACULTY_BODY,
    readiness_status: "NO_DATA",
    reason: "Not enough current-semester academic data is available",
    subjects: [],
    prediction_count: 0,
  }
  route("/predict/m1v2/STU-MISSING", 200, NO_DATA_BODY)

  const result = await facultyApi.getFacultyStudentM1V2("STU-MISSING")
  assert.equal(result.ok, true)
  if (result.ok) {
    assert.equal(result.data.readiness_status, "NO_DATA")
    assert.equal(result.data.subjects.length, 0)
  }
})

test("getFacultyStudentM1V2 rejects non-faculty / unlinked / anonymous", async () => {
  activeSession = null
  const anon = await facultyApi.getFacultyStudentM1V2("STU-A")
  assert.equal(anon.ok, false)
  if (!anon.ok) assert.equal(anon.error.status, 401)

  activeSession = { ...DEFAULT_SESSION, role: "Student", student_id: "STU-A" }
  const wrongRole = await facultyApi.getFacultyStudentM1V2("STU-A")
  assert.equal(wrongRole.ok, false)
  if (!wrongRole.ok) assert.equal(wrongRole.error.status, 403)

  activeSession = { ...DEFAULT_SESSION, faculty_id: null }
  const unlinked = await facultyApi.getFacultyStudentM1V2("STU-A")
  assert.equal(unlinked.ok, false)
  if (!unlinked.ok) {
    assert.equal(unlinked.error.status, 400)
    assert.equal(unlinked.error.code, "unlinked")
  }
  assert.equal(getCalls("/predict/m1v2").length, 0)
})

// ---------------------------------------------------------------------------
// getFacultyStudentM2V2 — M2 V2 Next-Semester Performance Prediction
// Hits the generic /predict/m2v2/{student_id} route (NOT under /faculty/) with
// the Faculty bearer token. Server-side authorize_prediction_access enforces
// faculty scope.
// ---------------------------------------------------------------------------

const M2V2_FACULTY_BODY = {
  student_id: "STU-A",
  model_id: "m2_v2",
  model_version: "2.0",
  readiness_status: "READY",
  observation_semester: 6,
  prediction_takes_effect_semester: 7,
  predicted_next_semester_sgpa: 7.88,
  predicted_next_semester_percentage: 71.5,
  algorithm: { next_semester_sgpa: "random_forest", next_semester_percentage: "ridge" },
  reason: null,
  predicted_at: "2026-09-01T08:00:00Z",
  inference_ms: 2.0,
  note: "Predicted next-semester SGPA/percentage are model estimates.",
}

test("getFacultyStudentM2V2 hits the generic predict route with faculty auth", async () => {
  route("/predict/m2v2/STU-A", 200, M2V2_FACULTY_BODY)

  const result = await facultyApi.getFacultyStudentM2V2("STU-A")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.model_id, "m2_v2")
  assert.equal(result.data.readiness_status, "READY")
  assert.equal(result.data.prediction_takes_effect_semester, 7)

  const hit = getCalls("/predict/m2v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m2v2/STU-A")
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("getFacultyStudentM2V2 URL-encodes the student id", async () => {
  route("/predict/m2v2/STU%20A%2F1", 200, M2V2_FACULTY_BODY)

  const result = await facultyApi.getFacultyStudentM2V2("STU A/1")
  assert.equal(result.ok, true)
  const hit = getCalls("/predict/m2v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m2v2/STU%20A%2F1")
})

test("getFacultyStudentM2V2 caches per faculty+student within TTL", async () => {
  route("/predict/m2v2/STU-A", 200, M2V2_FACULTY_BODY)

  await facultyApi.getFacultyStudentM2V2("STU-A")
  await facultyApi.getFacultyStudentM2V2("STU-A")
  assert.equal(getCalls("/predict/m2v2").length, 1)
})

test("getFacultyStudentM2V2 maps 404 (NO_DATA / out of scope) to not_found", async () => {
  route("/predict/m2v2/STU-MISSING", 404, { detail: "no record" })

  const result = await facultyApi.getFacultyStudentM2V2("STU-MISSING")
  assert.equal(result.ok, false)
  if (result.ok) return
  assert.equal(result.error.code, "not_found")
})

test("getFacultyStudentM2V2 rejects non-faculty / unlinked / anonymous", async () => {
  activeSession = null
  const anon = await facultyApi.getFacultyStudentM2V2("STU-A")
  assert.equal(anon.ok, false)
  if (!anon.ok) assert.equal(anon.error.status, 401)

  activeSession = { ...DEFAULT_SESSION, role: "Student", student_id: "STU-A" }
  const wrongRole = await facultyApi.getFacultyStudentM2V2("STU-A")
  assert.equal(wrongRole.ok, false)
  if (!wrongRole.ok) assert.equal(wrongRole.error.status, 403)

  activeSession = { ...DEFAULT_SESSION, faculty_id: null }
  const unlinked = await facultyApi.getFacultyStudentM2V2("STU-A")
  assert.equal(unlinked.ok, false)
  if (!unlinked.ok) {
    assert.equal(unlinked.error.status, 400)
    assert.equal(unlinked.error.code, "unlinked")
  }
  assert.equal(getCalls("/predict/m2v2").length, 0)
})

// ---------------------------------------------------------------------------
// getFacultyStudentM3V2 — M3 V2 At-Risk Student Prediction
// Hits the generic /predict/m3v2/{student_id} route (NOT under /faculty/) with
// the Faculty bearer token. probability_at_risk is a model ESTIMATE surfaced by
// the backend for this role.
// ---------------------------------------------------------------------------

const M3V2_FACULTY_BODY = {
  student_id: "STU-A",
  model_id: "m3_v2",
  model_version: "2.0",
  readiness_status: "READY",
  observation_semester: 6,
  prediction_takes_effect_semester: 7,
  probability_at_risk: 0.12,
  threshold: 0.64,
  is_estimated_at_risk: false,
  signals: [{ feature: "semester_sgpa", raw_value: 7.5, importance: 0.24 }],
  algorithm: { is_at_risk_next_sem: "random_forest" },
  reason: null,
  predicted_at: "2026-09-01T08:00:00Z",
  inference_ms: 2.0,
  note: "Estimated academic-risk probability is a model estimate.",
}

test("getFacultyStudentM3V2 hits the generic predict route with faculty auth", async () => {
  route("/predict/m3v2/STU-A", 200, M3V2_FACULTY_BODY)

  const result = await facultyApi.getFacultyStudentM3V2("STU-A")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.model_id, "m3_v2")
  assert.equal(result.data.readiness_status, "READY")
  assert.equal(result.data.prediction_takes_effect_semester, 7)
  assert.equal(result.data.probability_at_risk, 0.12)
  assert.equal(result.data.is_estimated_at_risk, false)

  const hit = getCalls("/predict/m3v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m3v2/STU-A")
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("getFacultyStudentM3V2 URL-encodes the student id and caches within TTL", async () => {
  route("/predict/m3v2/STU%20A%2F1", 200, M3V2_FACULTY_BODY)

  const result = await facultyApi.getFacultyStudentM3V2("STU A/1")
  assert.equal(result.ok, true)
  const hit = getCalls("/predict/m3v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m3v2/STU%20A%2F1")

  await facultyApi.getFacultyStudentM3V2("STU A/1")
  assert.equal(getCalls("/predict/m3v2").length, 1)
})

test("getFacultyStudentM3V2 maps 404 (NO_DATA / out of scope) to not_found", async () => {
  route("/predict/m3v2/STU-MISSING", 404, { detail: "no record" })

  const result = await facultyApi.getFacultyStudentM3V2("STU-MISSING")
  assert.equal(result.ok, false)
  if (result.ok) return
  assert.equal(result.error.code, "not_found")
})

test("getFacultyStudentM3V2 rejects non-faculty / unlinked / anonymous", async () => {
  activeSession = null
  const anon = await facultyApi.getFacultyStudentM3V2("STU-A")
  assert.equal(anon.ok, false)
  if (!anon.ok) assert.equal(anon.error.status, 401)

  activeSession = { ...DEFAULT_SESSION, role: "Student", student_id: "STU-A" }
  const wrongRole = await facultyApi.getFacultyStudentM3V2("STU-A")
  assert.equal(wrongRole.ok, false)
  if (!wrongRole.ok) assert.equal(wrongRole.error.status, 403)

  activeSession = { ...DEFAULT_SESSION, faculty_id: null }
  const unlinked = await facultyApi.getFacultyStudentM3V2("STU-A")
  assert.equal(unlinked.ok, false)
  if (!unlinked.ok) {
    assert.equal(unlinked.error.status, 400)
    assert.equal(unlinked.error.code, "unlinked")
  }
  assert.equal(getCalls("/predict/m3v2").length, 0)
})
