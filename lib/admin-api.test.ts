// Frontend tests for the MD-05 admin BFF layer (lib/admin-api.ts).
//
// Runs with Node's built-in test runner + TypeScript type stripping:
//   node --experimental-test-module-mocks --test lib/admin-api.test.ts
//
// Covers the MD-05 contracts without a live FastAPI:
//   * auth gating (401 no session / 403 wrong role)
//   * getAdminStudents query-string building (filters, risk, search, sort,
//     pagination) and empty-query omission
//   * getAdminFaculty contract fetch
//   * HTTP error -> BffError mapping

import { test, mock, beforeEach } from "node:test"
import assert from "node:assert/strict"

// ---------------------------------------------------------------------------
// Session mock. Registered BEFORE admin-api is imported so that the real
// student-session.ts (which imports next/headers, not resolvable in plain
// Node) is never loaded.
// ---------------------------------------------------------------------------

let activeSession: unknown = null

mock.module("./student-session.ts", {
  namedExports: {
    getSessionUser: async () => activeSession,
  },
})

const adminApi = await import("./admin-api.ts")

// ---------------------------------------------------------------------------
// Fetch mock
// ---------------------------------------------------------------------------

const DEFAULT_SESSION = {
  user_id: "u-1",
  username: "admin",
  role: "Admin",
  department: "Admin",
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
  installFetchMock()
})

function getCalls(substring: string): FetchCall[] {
  return calls.filter((c) => c.url.includes(substring))
}

const baseUrl = "http://localhost:8000/api/v1/admin"

// ---------------------------------------------------------------------------
// Auth gating
// ---------------------------------------------------------------------------

test("no session -> 401 unauthorized, fetch never called", async () => {
  activeSession = null
  const result = await adminApi.getAdminFaculty()
  assert.equal(result.ok, false)
  assert.equal(calls.length, 0)
})

test("non-admin role -> 403 unauthorized", async () => {
  activeSession = { ...DEFAULT_SESSION, role: "Student" }
  const result = await adminApi.getAdminStudents()
  assert.equal(result.ok, false)
  assert.equal(result.ok ? "" : result.error.status, 403)
})

// ---------------------------------------------------------------------------
// getAdminStudents query building
// ---------------------------------------------------------------------------

test("getAdminStudents forwards filters, risk, search, sort and pagination", async () => {
  const body = {
    filters: { academic_years: ["2025-26", "2026-27"], departments: [], semesters: [1, 7] },
    students: [],
    students_total: 0,
    limit: 50,
    offset: 50,
    sort_by: "sgpa",
    sort_dir: "desc",
    generated_at: "2026-08-12T00:00:00Z",
  }
  route("students", 200, body)

  const result = await adminApi.getAdminStudents({
    filters: { department_code: 1, academic_year: "2026-27", semester: 7 },
    risk: "High",
    search: "rahul",
    sortBy: "sgpa",
    sortDir: "desc",
    limit: 50,
    offset: 50,
  })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.offset, 50)
  assert.equal(result.data.sort_by, "sgpa")

  const hit = getCalls("students")
  assert.equal(hit.length, 1)
  const query = hit[0].url.split("?")[1] ?? ""
  assert.ok(query.includes("department_code=1"))
  assert.ok(query.includes("academic_year=2026-27"))
  assert.ok(query.includes("semester=7"))
  assert.ok(query.includes("risk=High"))
  assert.ok(query.includes("search=rahul"))
  assert.ok(query.includes("sort_by=sgpa"))
  assert.ok(query.includes("sort_dir=desc"))
  assert.ok(query.includes("limit=50"))
  assert.ok(query.includes("offset=50"))

  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("getAdminStudents with no query hits the plain students endpoint", async () => {
  const body = {
    filters: { academic_years: [], departments: [], semesters: [] },
    students: [],
    students_total: 0,
    limit: 100,
    offset: 0,
    sort_by: "name",
    sort_dir: "asc",
    generated_at: "2026-08-12T00:00:00Z",
  }
  route("students", 200, body)

  const result = await adminApi.getAdminStudents()
  assert.equal(result.ok, true)
  assert.equal(getCalls("students")[0].url, `${baseUrl}/students`)
})

// ---------------------------------------------------------------------------
// getAdminFaculty contract
// ---------------------------------------------------------------------------

test("getAdminFaculty fetches the faculty overview contract", async () => {
  const body = {
    kpis: { total_faculty: 20, active_faculty: 18, department_count: 4 },
    by_department: [
      { department_code: 1, department_name: "CSE", count: 8 },
      { department_code: 2, department_name: "BBA", count: 4 },
    ],
    by_designation: [
      { designation: "Professor", count: 6 },
      { designation: "Unassigned", count: 2 },
    ],
    faculty: [
      {
        faculty_id: "FAC000001",
        faculty_code: "FAC-CSE-001",
        full_name: "Dr. A Sharma",
        department_code: 1,
        department_name: "CSE",
        designation: "Professor",
        subject_count: 2,
        student_count: 120,
        workload_hours: 10.5,
      },
    ],
    generated_at: "2026-08-12T00:00:00Z",
  }
  route("faculty", 200, body)

  const result = await adminApi.getAdminFaculty()
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.kpis.total_faculty, 20)
  assert.equal(result.data.kpis.active_faculty, 18)
  assert.equal(result.data.kpis.department_count, 4)
  assert.equal(result.data.by_designation.length, 2)
  assert.equal(result.data.faculty[0].workload_hours, 10.5)
  assert.equal(getCalls("faculty")[0].url, `${baseUrl}/faculty`)
})

// ---------------------------------------------------------------------------
// Error mapping
// ---------------------------------------------------------------------------

test("error mapping for admin endpoints (401/403/422/503/500)", async () => {
  const cases: Array<[number, string]> = [
    [401, "unauthorized"],
    [403, "unauthorized"],
    [422, "invalid"],
    [503, "unavailable"],
    [500, "server_error"],
  ]
  for (const [status, code] of cases) {
    route("students", status, { detail: "x" })
    // Unique search keeps each call off the shared 60s BFF cache.
    const result = await adminApi.getAdminStudents({ search: `q-${status}` })
    assert.equal(result.ok, false)
    if (result.ok) continue
    assert.equal(result.error.code, code, `status ${status} should map to ${code}`)
    assert.equal(result.error.status, status)
  }
})

// ---------------------------------------------------------------------------
// MD-07 Announcements & Executive Summary
// ---------------------------------------------------------------------------

test("createAnnouncement POSTs notification body and returns result", async () => {
  const body = {
    announcement_id: "announcement:123:456",
    title: "Exam Notice",
    type: "ACADEMIC_NOTICE",
    target_audience: "both",
    recipients_notified: 90,
    created_at: "2026-08-12T00:00:00Z",
  }
  route("announcements", 201, body)

  const result = await adminApi.createAnnouncement({
    title: "Exam Notice",
    message: "Exams start on Monday.",
    type: "ACADEMIC_NOTICE",
    target_audience: "both",
    priority: "High",
  })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.announcement_id, "announcement:123:456")
  assert.equal(result.data.recipients_notified, 90)

  const hit = getCalls("announcements")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].init?.method, "POST")
})

test("getExecutiveSummary fetches grounded insights contract", async () => {
  const body = {
    strongest_department: {
      department_code: 1,
      department_name: "CSE",
      student_count: 40,
      avg_cgpa: 8.2,
      avg_percentage: 82.0,
    },
    weakest_department: null,
    weakest_subject: null,
    attendance_concern_department: "BBA",
    attendance_shortage_count: 10,
    total_at_risk_students: 15,
    high_risk_count: 10,
    critical_risk_count: 5,
    top_risk_department: "CSE",
    total_students: 80,
    overall_avg_cgpa: 7.6,
    overall_attendance_pct: 78.0,
    internship_completion_rate: 62.5,
    insights: [
      "Strongest Department: CSE leads performance.",
      "Risk Early Warning: 15 students flagged At-Risk.",
    ],
    generated_at: "2026-08-12T00:00:00Z",
  }
  route("executive-summary", 200, body)

  const result = await adminApi.getExecutiveSummary()
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.total_students, 80)
  assert.equal(result.data.insights.length, 2)
  assert.equal(getCalls("executive-summary")[0].url, `${baseUrl}/executive-summary`)
})

test("getAdminMLIntelligence fetches ML intelligence bundle", async () => {
  const body = {
    overview: {
      total_students: 80,
      students_with_predictions: 40,
      coverage_percentage: 50.0,
      total_predictions: 160,
      models_status: { m1: "active", m2: "active", m3: "active", m4: "active" },
    },
    future_risk: {
      future_at_risk_count: 5,
      future_at_risk_percentage: 12.5,
      future_low_risk_count: 35,
      current_deterministic_high_critical_count: 8,
      future_risk_by_department: [],
      future_risk_by_semester: [],
      disclaimer: "M3 is a machine learning future-risk prediction model forecasting next-semester risk.",
    },
    academic_predictions: {
      m1: {
        total_subject_predictions: 50,
        predicted_avg_subject_mark: 45.2,
        department_subject_performance: [],
        subjects_needing_attention: [],
      },
      m2: {
        predicted_avg_next_sgpa: 7.5,
        predicted_avg_next_percentage: 72.0,
        sgpa_distribution: [],
        percentage_distribution: [],
        department_performance_distribution: [],
        disclaimer: "M2 forecasts next-semester SGPA and percentage.",
      },
    },
    career_readiness: {
      avg_career_readiness_score: 78.5,
      readiness_level_counts: { High: 20, Medium: 15, Low: 5 },
      department_readiness_distribution: [],
      top_positive_factors: [],
      top_risk_factors: [],
      disclaimer: "M4 is a deterministic rule-based scoring engine.",
    },
    executive_insights: [
      {
        category: "Future Risk Intelligence",
        title: "Future Risk Forecast",
        detail: "M3 ML model forecasts 5 students at future risk.",
        priority: "high",
      },
    ],
    filter_options: {
      departments: [
        { department_code: 1, department_name: "Computer Science and Engineering", student_count: 50 },
        { department_code: 2, department_name: "Bachelor of Business Administration", student_count: 30 },
      ],
      semesters: [
        { semester_no: 5, student_count: 30 },
        { semester_no: 7, student_count: 50 },
      ],
    },
    generated_at: "2026-08-13T10:00:00Z",
  }

  route("ml-intelligence?department_code=1", 200, body)

  const result = await adminApi.getAdminMLIntelligence({ department_code: 1 })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.overview.total_students, 80)
  assert.equal(result.data.future_risk.future_at_risk_count, 5)
  assert.equal(result.data.executive_insights.length, 1)
  assert.equal(result.data.filter_options.departments.length, 2)
  assert.deepEqual(
    result.data.filter_options.semesters.map((s) => s.semester_no),
    [5, 7],
  )
  assert.equal(getCalls("ml-intelligence")[0].url, `${baseUrl}/ml-intelligence?department_code=1`)
})

// ---------------------------------------------------------------------------
// ML-12 §12.5 getAdminMlFeedbackHealth
// ---------------------------------------------------------------------------

const ML_FEEDBACK_HEALTH_BODY = {
  total: 5,
  confirmed: 3,
  dismissed: 2,
  pending: 7,
  by_action: [
    { action: "confirmed", count: 3 },
    { action: "dismissed", count: 2 },
  ],
  by_department: [
    {
      department_code: 1,
      department_name: "Computer Science and Engineering",
      reviewed: 5,
      confirmed: 3,
      dismissed: 2,
    },
  ],
  by_semester: [
    { semester_no: 5, reviewed: 5, confirmed: 3, dismissed: 2 },
  ],
  disclaimer: "Faculty reviews are estimates gathered for model improvement only.",
}

test("getAdminMlFeedbackHealth fetches the admin feedback endpoint", async () => {
  route("ml-feedback", 200, ML_FEEDBACK_HEALTH_BODY)

  const result = await adminApi.getAdminMlFeedbackHealth()
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.total, 5)
  assert.equal(result.data.confirmed, 3)
  assert.equal(result.data.dismissed, 2)
  assert.equal(result.data.pending, 7)
  assert.equal(result.data.by_action.length, 2)
  assert.equal(result.data.by_department[0].department_name, "Computer Science and Engineering")
  assert.equal(getCalls("ml-feedback")[0].url, `${baseUrl}/ml-feedback`)
})

test("getAdminMlFeedbackHealth requires an admin session", async () => {
  activeSession = null
  const result = await adminApi.getAdminMlFeedbackHealth()
  assert.equal(result.ok, false)
  assert.equal(result.ok ? "" : result.error.status, 401)
  assert.equal(calls.length, 0)
})

// ---------------------------------------------------------------------------
// getAdminStudentM1V2 — M1 V2 Subject Marks Prediction (typed client only).
// The backend exposes M1 V2 per-student only (no cohort aggregate, not wired
// into persisted ml_predictions). The Admin UI documents this as a limitation
// and never fabricates cohort statistics; the typed client keeps the API
// surface complete for a future per-student drill-down.
// ---------------------------------------------------------------------------

const M1V2_ADMIN_BODY = {
  student_id: "STU-X",
  model_id: "m1_v2",
  model_version: "2.0",
  algorithm: "ridge",
  readiness_status: "READY",
  reason: null,
  current_semester: 5,
  prediction_count: 1,
  predicted_at: "2026-09-01T08:00:00Z",
  inference_ms: 3.2,
  subjects: [
    {
      subject_id: "SUB001",
      semester_no: 5,
      predicted_end_sem_marks: 58.0,
      target_max: 70,
      grade_band: "Above Average",
      grade_label: "A-",
      input_features: {
        internal_marks: 18.0,
        mid_sem_marks: 15.0,
        att_total_pct: 90.0,
        pre_endsem_assessment_pct: 68.0,
      },
    },
  ],
  note: "Predicted end-sem marks are model estimates, not actual results.",
}

test("getAdminStudentM1V2 hits the generic predict route with admin auth", async () => {
  route("/predict/m1v2/STU-X", 200, M1V2_ADMIN_BODY)

  const result = await adminApi.getAdminStudentM1V2("STU-X")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.model_id, "m1_v2")
  assert.equal(result.data.readiness_status, "READY")
  assert.equal(result.data.subjects[0].grade_band, "Above Average")

  const hit = getCalls("/predict/m1v2")
  assert.equal(hit.length, 1)
  // Generic predict route (NOT under /admin/).
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m1v2/STU-X")
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("getAdminStudentM1V2 URL-encodes the student id and caches within TTL", async () => {
  route("/predict/m1v2/STU%20A%2F2", 200, M1V2_ADMIN_BODY)

  const result = await adminApi.getAdminStudentM1V2("STU A/2")
  assert.equal(result.ok, true)
  const encodedHit = getCalls("/predict/m1v2")
  assert.equal(encodedHit.length, 1)
  assert.equal(encodedHit[0].url, "http://localhost:8000/api/v1/predict/m1v2/STU%20A%2F2")

  // Second read must hit the module cache for the same admin+student key.
  await adminApi.getAdminStudentM1V2("STU A/2")
  assert.equal(getCalls("/predict/m1v2").length, 1)
})

test("getAdminStudentM1V2 returns 200 with NO_DATA for unavailable predictions", async () => {
  const NO_DATA_BODY = {
    ...M1V2_ADMIN_BODY,
    readiness_status: "NO_DATA",
    reason: "Not enough current-semester academic data is available",
    subjects: [],
    prediction_count: 0,
  }
  route("/predict/m1v2/STU-NOPE", 200, NO_DATA_BODY)
  const result = await adminApi.getAdminStudentM1V2("STU-NOPE")
  assert.equal(result.ok, true)
  if (result.ok) {
    assert.equal(result.data.readiness_status, "NO_DATA")
    assert.equal(result.data.subjects.length, 0)
  }
})

test("getAdminStudentM1V2 maps 503 and gates non-admin", async () => {
  route("/predict/m1v2/STU-DOWN", 503, { detail: "down" })
  const down = await adminApi.getAdminStudentM1V2("STU-DOWN")
  assert.equal(down.ok, false)
  if (!down.ok) assert.equal(down.error.status, 503)

  activeSession = null
  const anon = await adminApi.getAdminStudentM1V2("STU-X")
  assert.equal(anon.ok, false)
  if (!anon.ok) assert.equal(anon.error.status, 401)

  activeSession = { ...DEFAULT_SESSION, role: "Faculty", faculty_id: "FAC-A" }
  const wrongRole = await adminApi.getAdminStudentM1V2("STU-X")
  assert.equal(wrongRole.ok, false)
  if (!wrongRole.ok) assert.equal(wrongRole.error.status, 403)
})

// ---------------------------------------------------------------------------
// getAdminStudentM2V2 — M2 V2 Next-Semester Performance Prediction (typed
// client only). Backend exposes M2 V2 per-student only; the Admin UI documents
// this as a limitation and never fabricates cohort statistics.
// ---------------------------------------------------------------------------

const M2V2_ADMIN_BODY = {
  student_id: "STU-X",
  model_id: "m2_v2",
  model_version: "2.0",
  readiness_status: "READY",
  observation_semester: 6,
  prediction_takes_effect_semester: 7,
  predicted_next_semester_sgpa: 8.45,
  predicted_next_semester_percentage: 80.0,
  algorithm: { next_semester_sgpa: "random_forest", next_semester_percentage: "ridge" },
  reason: null,
  predicted_at: "2026-09-01T08:00:00Z",
  inference_ms: 2.2,
  note: "Predicted next-semester SGPA/percentage are model estimates.",
}

test("getAdminStudentM2V2 hits the generic predict route with admin auth", async () => {
  route("/predict/m2v2/STU-X", 200, M2V2_ADMIN_BODY)

  const result = await adminApi.getAdminStudentM2V2("STU-X")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.model_id, "m2_v2")
  assert.equal(result.data.readiness_status, "READY")
  assert.equal(result.data.predicted_next_semester_sgpa, 8.45)

  const hit = getCalls("/predict/m2v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m2v2/STU-X")
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("getAdminStudentM2V2 URL-encodes the student id and caches within TTL", async () => {
  route("/predict/m2v2/STU%20A%2F2", 200, M2V2_ADMIN_BODY)

  const result = await adminApi.getAdminStudentM2V2("STU A/2")
  assert.equal(result.ok, true)
  const encodedHit = getCalls("/predict/m2v2")
  assert.equal(encodedHit.length, 1)
  assert.equal(encodedHit[0].url, "http://localhost:8000/api/v1/predict/m2v2/STU%20A%2F2")

  await adminApi.getAdminStudentM2V2("STU A/2")
  assert.equal(getCalls("/predict/m2v2").length, 1)
})

test("getAdminStudentM2V2 maps 404 / 503 and gates non-admin", async () => {
  route("/predict/m2v2/STU-NOPE", 404, { detail: "no record" })
  const missing = await adminApi.getAdminStudentM2V2("STU-NOPE")
  assert.equal(missing.ok, false)
  if (!missing.ok) assert.equal(missing.error.status, 404)

  route("/predict/m2v2/STU-DOWN", 503, { detail: "down" })
  const down = await adminApi.getAdminStudentM2V2("STU-DOWN")
  assert.equal(down.ok, false)
  if (!down.ok) assert.equal(down.error.status, 503)

  activeSession = null
  const anon = await adminApi.getAdminStudentM2V2("STU-X")
  assert.equal(anon.ok, false)
  if (!anon.ok) assert.equal(anon.error.status, 401)

  activeSession = { ...DEFAULT_SESSION, role: "Faculty", faculty_id: "FAC-A" }
  const wrongRole = await adminApi.getAdminStudentM2V2("STU-X")
  assert.equal(wrongRole.ok, false)
  if (!wrongRole.ok) assert.equal(wrongRole.error.status, 403)
})

// ---------------------------------------------------------------------------
// getAdminStudentM3V2 — M3 V2 At-Risk Student Prediction (typed client only).
// Backend exposes M3 V2 per-student only; the Admin UI honestly documents this
// as a limitation and never fabricates cohort at-risk statistics.
// ---------------------------------------------------------------------------

const M3V2_ADMIN_BODY = {
  student_id: "STU-X",
  model_id: "m3_v2",
  model_version: "2.0",
  readiness_status: "READY",
  observation_semester: 6,
  prediction_takes_effect_semester: 7,
  probability_at_risk: 0.18,
  threshold: 0.64,
  is_estimated_at_risk: false,
  signals: [{ feature: "backlog_count", raw_value: 0, importance: 0.31 }],
  algorithm: { is_at_risk_next_sem: "random_forest" },
  reason: null,
  predicted_at: "2026-09-01T08:00:00Z",
  inference_ms: 2.2,
  note: "Estimated academic-risk probability is a model estimate.",
}

test("getAdminStudentM3V2 hits the generic predict route with admin auth", async () => {
  route("/predict/m3v2/STU-X", 200, M3V2_ADMIN_BODY)

  const result = await adminApi.getAdminStudentM3V2("STU-X")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.model_id, "m3_v2")
  assert.equal(result.data.readiness_status, "READY")
  assert.equal(result.data.probability_at_risk, 0.18)
  assert.equal(result.data.is_estimated_at_risk, false)

  const hit = getCalls("/predict/m3v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m3v2/STU-X")
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("getAdminStudentM3V2 URL-encodes the student id and caches within TTL", async () => {
  route("/predict/m3v2/STU%20A%2F2", 200, M3V2_ADMIN_BODY)

  const result = await adminApi.getAdminStudentM3V2("STU A/2")
  assert.equal(result.ok, true)
  const encodedHit = getCalls("/predict/m3v2")
  assert.equal(encodedHit.length, 1)
  assert.equal(encodedHit[0].url, "http://localhost:8000/api/v1/predict/m3v2/STU%20A%2F2")

  await adminApi.getAdminStudentM3V2("STU A/2")
  assert.equal(getCalls("/predict/m3v2").length, 1)
})

test("getAdminStudentM3V2 maps 404 / 503 and gates non-admin", async () => {
  route("/predict/m3v2/STU-NOPE", 404, { detail: "no record" })
  const missing = await adminApi.getAdminStudentM3V2("STU-NOPE")
  assert.equal(missing.ok, false)
  if (!missing.ok) assert.equal(missing.error.status, 404)

  route("/predict/m3v2/STU-DOWN", 503, { detail: "down" })
  const down = await adminApi.getAdminStudentM3V2("STU-DOWN")
  assert.equal(down.ok, false)
  if (!down.ok) assert.equal(down.error.status, 503)

  activeSession = null
  const anon = await adminApi.getAdminStudentM3V2("STU-X")
  assert.equal(anon.ok, false)
  if (!anon.ok) assert.equal(anon.error.status, 401)

  activeSession = { ...DEFAULT_SESSION, role: "Faculty", faculty_id: "FAC-A" }
  const wrongRole = await adminApi.getAdminStudentM3V2("STU-X")
  assert.equal(wrongRole.ok, false)
  if (!wrongRole.ok) assert.equal(wrongRole.error.status, 403)
})


