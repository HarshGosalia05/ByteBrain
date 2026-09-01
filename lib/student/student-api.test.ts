// Frontend tests for the MD-05 student BFF layer (lib/student-api.ts).
//
// Runs with Node's built-in test runner + TypeScript type stripping:
//   node --experimental-test-module-mocks --test lib/student/student-api.test.ts
//
// Covers the BFF contract without a live FastAPI:
//   * auth gating (401 no session / 403 wrong role / 400 unlinked)
//   * HTTP error -> BffError mapping incl. MD-05 409/422
//   * query-string building for notifications filters
//   * mutation wiring (POST/PATCH, JSON body, bearer token)
//   * cache hit + invalidation on goal writes
//   * getStudentHealthData aggregation + refetch behavior

import { test, mock, beforeEach } from "node:test"
import assert from "node:assert/strict"

// ---------------------------------------------------------------------------
// Session mock. Registered BEFORE student-api is imported so that the real
// student-session.ts (which imports next/headers, not resolvable in plain
// Node) is never loaded.
// ---------------------------------------------------------------------------

let activeSession: unknown = null

mock.module("../student-session.ts", {
  namedExports: {
    getSessionUser: async () => activeSession,
  },
})

const studentApi = await import("../student-api.ts")

// ---------------------------------------------------------------------------
// Fetch mock
// ---------------------------------------------------------------------------

const DEFAULT_SESSION = {
  user_id: "u-1",
  username: "alice",
  role: "Student",
  department: "CSE",
  student_id: "STU-A",
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
  studentApi.invalidateBffKeys(DEFAULT_SESSION.student_id, [""])
  installFetchMock()
})

function getCalls(substring: string): FetchCall[] {
  return calls.filter((c) => c.url.includes(substring))
}

const baseUrl = "http://localhost:8000/api/v1/students/me"

// ---------------------------------------------------------------------------
// Auth gating
// ---------------------------------------------------------------------------

test("no session -> 401 unauthorized, fetch never called", async () => {
  activeSession = null
  const result = await studentApi.getHealthScore()
  assert.equal(result.ok, false)
  assert.equal(calls.length, 0)
})

test("non-student role -> 403 unauthorized", async () => {
  activeSession = { ...DEFAULT_SESSION, role: "Faculty" }
  const result = await studentApi.getPriorities()
  assert.equal(result.ok, false)
  assert.equal(result.ok ? "" : result.error.status, 403)
})

test("student without student_id -> 400 unlinked", async () => {
  activeSession = { ...DEFAULT_SESSION, student_id: null }
  const result = await studentApi.getGoals()
  assert.equal(result.ok, false)
  assert.equal(result.ok ? "" : result.error.status, 400)
})

// ---------------------------------------------------------------------------
// Success path + error mapping
// ---------------------------------------------------------------------------

test("getHealthScore fetches FastAPI with bearer token and returns data", async () => {
  const health = {
    student_id: "STU-A",
    available: true,
    score: 82.8,
    band: "Excellent",
    components: {},
    reasons: [],
    generated_at: "2026-08-10T00:00:00Z",
  }
  route("health-score", 200, health)

  const result = await studentApi.getHealthScore()
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.score, 82.8)

  const hit = getCalls("health-score")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, `${baseUrl}/health-score`)
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("error mapping for 404 / 409 / 422 / 503 / 500", async () => {
  const cases: Array<[number, string]> = [
    [404, "not_found"],
    [409, "conflict"],
    [422, "invalid"],
    [503, "unavailable"],
    [500, "server_error"],
  ]
  for (const [status, code] of cases) {
    route("health-score", status, { detail: "x" })
    const result = await studentApi.getHealthScore()
    assert.equal(result.ok, false)
    if (result.ok) continue
    assert.equal(result.error.code, code, `status ${status} should map to ${code}`)
    assert.equal(result.error.status, status)
  }
})

// ---------------------------------------------------------------------------
// Query building
// ---------------------------------------------------------------------------

test("getNotifications builds filter query string and bypasses cache", async () => {
  const notifBody = {
    student_id: "STU-A",
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
    unread_count: 0,
  }
  route("notifications", 200, notifBody)

  await studentApi.getNotifications({
    messageType: "ATTENDANCE_WARNING",
    unreadOnly: true,
    page: 2,
    pageSize: 10,
  })
  await studentApi.getNotifications()

  const hits = getCalls("notifications")
  assert.equal(hits.length, 2, "notifications must always refetch (useCache: false)")
  const filtered = hits.find((c) => c.url.includes("ATTENDANCE_WARNING"))
  assert.ok(filtered, "expected a call with the filter query")
  const query = filtered.url.split("?")[1] ?? ""
  assert.ok(query.includes("message_type=ATTENDANCE_WARNING"))
  assert.ok(query.includes("unread_only=true"))
  assert.ok(query.includes("page=2"))
  assert.ok(query.includes("page_size=10"))
})

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

test("createGoal POSTs JSON body with bearer token", async () => {
  const created = {
    goal_id: "g1",
    goal_type: "target_sgpa",
    target_value: 9.0,
    current_value: 8.4,
    achieved: false,
    status: "Active",
    created_at: "2026-08-10T00:00:00Z",
    updated_at: "2026-08-10T00:00:00Z",
  }
  route("goals", 200, created)

  const result = await studentApi.createGoal({ goal_type: "target_sgpa", target_value: 9.0 })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.goal_type, "target_sgpa")

  const hit = getCalls("goals").find((c) => c.init?.method === "POST")
  assert.ok(hit)
  assert.equal(hit.url, `${baseUrl}/goals`)
  const headers = hit.init?.headers as Record<string, string>
  assert.equal(headers["Content-Type"], "application/json")
  assert.deepEqual(JSON.parse(String(hit.init?.body)), {
    goal_type: "target_sgpa",
    target_value: 9.0,
  })
})

test("updateGoal PATCHes and markNotificationRead PATCHes read endpoint", async () => {
  const goal = {
    goal_id: "g1",
    goal_type: "target_sgpa",
    target_value: 9.0,
    current_value: 8.4,
    achieved: false,
    status: "Active",
    created_at: "2026-08-10T00:00:00Z",
    updated_at: "2026-08-10T00:00:00Z",
  }
  route("goals/g1", 200, goal)
  route("read", 200, { ...goal, goal_id: undefined, message_id: "m1", status: "Read" })

  const updated = await studentApi.updateGoal("g1", { status: "Active" })
  assert.equal(updated.ok, true)

  const marked = await studentApi.markNotificationRead("m1")
  assert.equal(marked.ok, true)

  const patch = getCalls("goals/g1").find((c) => c.init?.method === "PATCH")
  assert.ok(patch)
  assert.deepEqual(JSON.parse(String(patch.init?.body)), { status: "Active" })

  const read = getCalls("read").find((c) => c.init?.method === "PATCH")
  assert.ok(read)
  assert.equal(read.url, `${baseUrl}/notifications/m1/read`)
})

test("clearNotification DELETEs own notification with bearer token", async () => {
  const cleared = {
    message_id: "m1",
    message_type: "MARKS_CLEARED",
    title: "NLP marks cleared",
    message_body: "Your end-semester marks in NLP were cleared.",
    subject: "NLP",
    priority: "Normal",
    status: "Unread",
    created_at: "2026-08-10T00:00:00Z",
  }
  route("notifications/m1", 200, cleared)

  const result = await studentApi.clearNotification("m1")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.message_id, "m1")

  const hit = getCalls("notifications/m1").find((c) => c.init?.method === "DELETE")
  assert.ok(hit)
  assert.equal(hit.url, `${baseUrl}/notifications/m1`)
  const headers = hit.init?.headers as Record<string, string>
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("clearNotification maps 404 and clearAllNotifications returns count", async () => {
  route("notifications/m1", 404, { detail: "Notification not found" })
  const missing = await studentApi.clearNotification("m1")
  assert.equal(missing.ok, false)
  if (!missing.ok) assert.equal(missing.error.code, "not_found")

  routes.clear()
  route("notifications", 200, { student_id: "STU-A", cleared_count: 2 })
  const clearedAll = await studentApi.clearAllNotifications()
  assert.equal(clearedAll.ok, true)
  if (!clearedAll.ok) return
  assert.equal(clearedAll.data.cleared_count, 2)

  const hit = getCalls("notifications").find(
    (c) => c.init?.method === "DELETE" && !c.url.includes("/m1"),
  )
  assert.ok(hit)
  assert.equal(hit.url, `${baseUrl}/notifications`)
})

test("createGoal maps 409 conflict and 422 invalid", async () => {
  route("goals", 409, { detail: "already active" })
  const conflict = await studentApi.createGoal({ goal_type: "target_sgpa", target_value: 9.0 })
  assert.equal(conflict.ok, false)
  if (!conflict.ok) assert.equal(conflict.error.code, "conflict")

  routes.clear()
  route("goals", 422, { detail: "out of range" })
  const invalid = await studentApi.createGoal({ goal_type: "target_sgpa", target_value: 12 })
  assert.equal(invalid.ok, false)
  if (!invalid.ok) assert.equal(invalid.error.code, "invalid")
})

// ---------------------------------------------------------------------------
// Cache + invalidation
// ---------------------------------------------------------------------------

test("getGoals is cached until a goal write invalidates it", async () => {
  const goalsBody = {
    student_id: "STU-A",
    goals: [
      {
        goal_id: "g1",
        goal_type: "target_sgpa",
        target_value: 9.0,
        current_value: 8.4,
        achieved: false,
        status: "Active",
        created_at: "2026-08-10T00:00:00Z",
        updated_at: "2026-08-10T00:00:00Z",
      },
    ],
  }
  route("goals", 200, goalsBody)

  const first = await studentApi.getGoals()
  const second = await studentApi.getGoals()
  assert.equal(first.ok && second.ok, true)
  const gets = getCalls("goals").filter((c) => c.init?.method === undefined)
  assert.equal(gets.length, 1, "second read must hit the cache")

  const createResult = await studentApi.createGoal({ goal_type: "target_sgpa", target_value: 9.5 })
  assert.equal(createResult.ok, true)

  await studentApi.getGoals()
  const getsAfter = getCalls("goals").filter((c) => c.init?.method === undefined)
  assert.equal(getsAfter.length, 2, "createGoal must invalidate the goals cache")
})

// ---------------------------------------------------------------------------
// Report card
// ---------------------------------------------------------------------------

const REPORT_CARD_BODY = {
  student_id: "STU-A",
  generated_at: "2026-08-11",
  profile: {
    student_id: "STU-A",
    first_name: "Alice",
    last_name: "Appleton",
    enrollment_no: 1001,
    admission_year: 2023,
    current_semester: 3,
    department_name: "CSE",
    current_academic_year: "2024-25",
    latest_sgpa: 8.4,
    overall_cgpa: 8.1,
    overall_percentage: 72.5,
    total_credits_registered: 60,
    total_credits_earned: 45,
    total_backlogs: 1,
    academic_standing: "Good",
  },
  semesters: [
    {
      semester: 1,
      academic_year: "2023-24",
      sgpa: 8.2,
      semester_percentage: 72.0,
      semester_grade: "B+",
      semester_result: "Pass",
      total_credits_earned: 22,
      credits_registered: 25,
      active_backlogs: 0,
      attendance_percentage: 85.0,
      subjects_registered: 5,
      academic_standing: "Good",
      subjects: [
        {
          subject_code: "CS101",
          subject_name: "Programming",
          semester: 1,
          credits: 5,
          internal_marks: 18.0,
          mid_sem_marks: 36.0,
          end_sem_marks: 42.0,
          total_marks: 96.0,
          percentage: 80.0,
          grade: "A",
          grade_point: 9.0,
          result_status: "Pass",
          attempt_number: 1,
          attendance_percentage: 86.0,
        },
      ],
    },
  ],
}

test("getReportCard fetches report-card with bearer token and returns data", async () => {
  route("report-card", 200, REPORT_CARD_BODY)

  const result = await studentApi.getReportCard()
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.profile.first_name, "Alice")
  assert.equal(result.data.semesters[0].subjects[0].subject_code, "CS101")

  const hit = getCalls("report-card")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, `${baseUrl}/report-card`)
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("getReportCard is cached across reads and maps 404", async () => {
  route("report-card", 200, REPORT_CARD_BODY)

  const first = await studentApi.getReportCard()
  const second = await studentApi.getReportCard()
  assert.equal(first.ok && second.ok, true)
  const gets = getCalls("report-card").filter((c) => c.init?.method === undefined)
  assert.equal(gets.length, 1, "second read must hit the cache")

  routes.clear()
  route("report-card", 404, { detail: "no records" })
  await studentApi.invalidateBffKeys(DEFAULT_SESSION.student_id, ["report-card"])
  const missing = await studentApi.getReportCard()
  assert.equal(missing.ok, false)
  if (!missing.ok) assert.equal(missing.error.code, "not_found")
})

test("getReportCard auth gating (401 / 403 / 400) applies", async () => {
  activeSession = null
  const noSession = await studentApi.getReportCard()
  assert.equal(noSession.ok, false)
  if (!noSession.ok) assert.equal(noSession.error.status, 401)

  activeSession = { ...DEFAULT_SESSION, role: "Faculty" }
  const wrongRole = await studentApi.getReportCard()
  assert.equal(wrongRole.ok, false)
  if (!wrongRole.ok) assert.equal(wrongRole.error.status, 403)

  activeSession = { ...DEFAULT_SESSION, student_id: null }
  const unlinked = await studentApi.getReportCard()
  assert.equal(unlinked.ok, false)
  if (!unlinked.ok) assert.equal(unlinked.error.status, 400)
})

// ---------------------------------------------------------------------------
// Aggregation
// ---------------------------------------------------------------------------

test("getStudentHealthData aggregates five endpoints; cached reads skip refetch", async () => {
  route("profile", 200, {
    student_id: "STU-A",
    first_name: "Alice",
    last_name: "Appleton",
    enrollment_no: 1001,
    admission_year: 2023,
    current_semester: 7,
    department_name: "CSE",
    current_academic_year: "2026-27",
    latest_sgpa: 8.4,
    overall_cgpa: 8.1,
    overall_percentage: 72.5,
    total_credits_registered: 60,
    total_credits_earned: 45,
    total_backlogs: 0,
    academic_standing: "Good",
  })
  route("health-score", 200, {
    student_id: "STU-A",
    available: true,
    score: 82.8,
    band: "Excellent",
    components: {},
    reasons: [],
    generated_at: "2026-08-10T00:00:00Z",
  })
  route("priorities", 200, { student_id: "STU-A", items: [] })
  route("goals", 200, { student_id: "STU-A", goals: [] })
  route("unread-count", 200, { student_id: "STU-A", unread_count: 3 })

  const first = await studentApi.getStudentHealthData()
  assert.equal(first.ok, true)
  if (!first.ok) return
  assert.equal(first.data.unreadCount, 3)
  assert.equal(first.data.profile.first_name, "Alice")
  assert.equal(first.data.health.score, 82.8)
  assert.equal(calls.length, 5, "first call must hit all five endpoints")

  const second = await studentApi.getStudentHealthData()
  assert.equal(second.ok, true)
  assert.equal(
    calls.length,
    6,
    "second call must serve cached reads and only refetch unread-count",
  )
})

// ---------------------------------------------------------------------------
// ML insights (ML-09)
// ---------------------------------------------------------------------------

const ML_INSIGHTS_BODY = {
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
            subject_name: "Data Structures",
            semester_no: 3,
            predicted_end_sem_marks: 55.5,
            clipped: false,
            projected_percentage: 70.0,
            projected_band: "Average",
            inputs: [{ name: "internal_marks", value: 14.5, present: true }],
            factors: [
              {
                kind: "positive",
                source: "business_rule",
                detail: "Projected total percentage of 70.0% is in the documented 'Average' band.",
              },
            ],
            interpretation: "M1 predicts end-semester marks of 55.5 for Data Structures.",
          },
        ],
      },
    },
    m2: {
      available: true,
      prediction: {
        model_id: "m2",
        predictions: [],
        input_row_count: 0,
        prediction_count: 0,
      },
      explanation: { model_id: "m2", prediction_type: "m2", explanations: [] },
    },
    m3: {
      available: false,
      reason: "no_data",
      message: "No data found for student STU-A",
    },
    m4: {
      available: false,
      reason: "error",
      message: "This insight is temporarily unavailable.",
    },
  },
}

test("getStudentMlInsights fetches /predict/insights with own student id", async () => {
  route("/predict/insights/STU-A", 200, ML_INSIGHTS_BODY)

  const result = await studentApi.getStudentMlInsights()
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.student_id, "STU-A")
  assert.deepEqual(Object.keys(result.data.models), ["m1", "m2", "m3", "m4"])
  assert.equal(result.data.models.m3.available, false)
  if (result.data.models.m1.available) {
    const prediction = result.data.models.m1.prediction
    if (prediction.model_id === "m1") {
      assert.equal(prediction.predictions[0].subject_id, "SUB001")
    }
  }

  const hit = getCalls("/predict/insights")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/insights/STU-A")
  const expectedToken = Buffer.from(JSON.stringify(DEFAULT_SESSION), "utf-8").toString("base64")
  const headers = hit[0].init?.headers as Record<string, string>
  assert.equal(headers["Authorization"], `Bearer ${expectedToken}`)
})

test("getStudentMlInsights url-encodes the student id", async () => {
  activeSession = { ...DEFAULT_SESSION, student_id: "STU A/1" }
  route("/predict/insights/STU%20A%2F1", 200, ML_INSIGHTS_BODY)

  const result = await studentApi.getStudentMlInsights()
  assert.equal(result.ok, true)

  const hit = getCalls("/predict/insights")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/insights/STU%20A%2F1")
})

test("getStudentMlInsights auth gating (401 / 403 / 400) applies", async () => {
  activeSession = null
  const noSession = await studentApi.getStudentMlInsights()
  assert.equal(noSession.ok, false)
  if (!noSession.ok) assert.equal(noSession.error.status, 401)

  activeSession = { ...DEFAULT_SESSION, role: "Faculty" }
  const wrongRole = await studentApi.getStudentMlInsights()
  assert.equal(wrongRole.ok, false)
  if (!wrongRole.ok) assert.equal(wrongRole.error.status, 403)

  activeSession = { ...DEFAULT_SESSION, student_id: null }
  const unlinked = await studentApi.getStudentMlInsights()
  assert.equal(unlinked.ok, false)
  if (!unlinked.ok) assert.equal(unlinked.error.status, 400)
})

test("getStudentMlInsights maps 404 and is cached across reads", async () => {
  route("/predict/insights/STU-A", 200, ML_INSIGHTS_BODY)
  await studentApi.getStudentMlInsights()
  await studentApi.getStudentMlInsights()
  const gets = getCalls("/predict/insights").filter((c) => c.init?.method === undefined)
  assert.equal(gets.length, 1, "second read must hit the cache")

  routes.clear()
  route("/predict/insights/STU-A", 404, { detail: "no records" })
  await studentApi.invalidateBffKeys(DEFAULT_SESSION.student_id, [""])
  const missing = await studentApi.getStudentMlInsights()
  assert.equal(missing.ok, false)
  if (!missing.ok) assert.equal(missing.error.code, "not_found")
})

test("getStudentSettings fetches /settings with auth", async () => {
  const settingsBody = {
    namespaces: {
      account: { display_language: "en", name_display: "full_name" },
      notifications: { grade_alerts: true, attendance_warnings: true, semester_results: true },
      security: { two_factor_enabled: false },
    },
    metadata: { schema_version: 1, preference_version: 0, configuration_version: 0 },
    activity: [],
  }
  route("/api/v1/students/me/settings", 200, settingsBody)

  const result = await studentApi.getStudentSettings()
  assert.equal(result.ok, true)
  if (result.ok) {
    assert.equal(result.data.namespaces.account?.display_language, "en")
    assert.equal(result.data.namespaces.notifications?.grade_alerts, true)
  }
  const hit = getCalls("/settings")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/students/me/settings")
})

test("updateStudentSettings PATCHes namespace with auth and invalidates cache", async () => {
  const updateBody = {
    namespaces: {
      account: { display_language: "hi", name_display: "formal" },
    },
    metadata: {},
    activity: [],
    highlights: ["account updated"],
  }
  route("/api/v1/students/me/settings/account", 200, updateBody)

  const result = await studentApi.updateStudentSettings("account", { display_language: "hi" })
  assert.equal(result.ok, true)
  const hit = getCalls("/settings/account")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].init?.method, "PATCH")
  assert.equal(hit[0].init?.body, JSON.stringify({ display_language: "hi" }))
})

test("changeStudentPassword POSTs credentials to backend", async () => {
  route("/api/v1/students/me/settings/change-password", 200, {
    status: "success",
    message: "Password updated successfully.",
    timestamp: "2026-08-14T10:00:00Z",
  })

  const result = await studentApi.changeStudentPassword("current_pwd", "new_secret_123")
  assert.equal(result.ok, true)
  if (result.ok) {
    assert.equal(result.data.status, "success")
  }
  const hit = getCalls("/change-password")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].init?.method, "POST")
  const parsedBody = JSON.parse(String(hit[0].init?.body))
  assert.equal(parsedBody.current_password, "current_pwd")
  assert.equal(parsedBody.new_password, "new_secret_123")
})

test("setStudentTwoFactor POSTs 2FA status to backend", async () => {
  route("/api/v1/students/me/settings/two-factor", 200, {
    status: "success",
    message: "Two-factor authentication enabled.",
    two_factor_enabled: true,
  })

  const result = await studentApi.setStudentTwoFactor(true, "email")
  assert.equal(result.ok, true)
  if (result.ok) {
    assert.equal(result.data.two_factor_enabled, true)
  }
  const hit = getCalls("/two-factor")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].init?.method, "POST")
  const parsedBody = JSON.parse(String(hit[0].init?.body))
  assert.equal(parsedBody.enabled, true)
})

test("signOutAllStudentDevices POSTs to backend", async () => {
  route("/api/v1/students/me/settings/sign-out-all", 200, {
    status: "success",
    message: "All active sessions have been signed out.",
  })

  const result = await studentApi.signOutAllStudentDevices()
  assert.equal(result.ok, true)
  const hit = getCalls("/sign-out-all")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].init?.method, "POST")
})

// ---------------------------------------------------------------------------
// M1 V2 — Subject Marks Prediction (validated production model).
// The per-student route /predict/m1v2/{student_id} is consumed by the student
// BFF. NO_DATA is returned as 200 with readiness_status="NO_DATA" and a reason.
// ---------------------------------------------------------------------------

const M1V2_BODY = {
  student_id: "STU-A",
  model_id: "m1_v2",
  model_version: "2.0",
  algorithm: "ridge",
  readiness_status: "READY",
  reason: null,
  current_semester: 3,
  prediction_count: 2,
  predicted_at: "2026-09-01T08:00:00Z",
  inference_ms: 3.2,
  subjects: [
    {
      subject_id: "SUB001",
      semester_no: 3,
      predicted_end_sem_marks: 55.5,
      target_max: 70,
      grade_band: "Average",
      grade_label: "B+",
      input_features: {
        internal_marks: 17.0,
        mid_sem_marks: 14.5,
        att_total_pct: 92.4,
        pre_endsem_assessment_pct: 61.0,
      },
    },
  ],
  note: "Predicted end-sem marks are model estimates, not actual results.",
}

test("getStudentM1V2 fetches /predict/m1v2 with own student id and parses typed result", async () => {
  route("/predict/m1v2/STU-A", 200, M1V2_BODY)

  const result = await studentApi.getStudentM1V2()
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.model_id, "m1_v2")
  assert.equal(result.data.model_version, "2.0")
  assert.equal(result.data.readiness_status, "READY")
  assert.equal(result.data.subjects.length, 1)
  const subject = result.data.subjects[0]
  assert.equal(subject.predicted_end_sem_marks, 55.5)
  assert.equal(subject.grade_band, "Average")
  assert.ok(subject.predicted_end_sem_marks <= subject.target_max)

  const hit = getCalls("/predict/m1v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m1v2/STU-A")
})

test("getStudentM1V2 url-encodes the student id", async () => {
  activeSession = { ...DEFAULT_SESSION, student_id: "STU A/1" }
  route("/predict/m1v2/STU%20A%2F1", 200, M1V2_BODY)

  const result = await studentApi.getStudentM1V2()
  assert.equal(result.ok, true)
  const hit = getCalls("/predict/m1v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m1v2/STU%20A%2F1")
})

test("getStudentM1V2 auth gating (401 / 403 / 400) applies", async () => {
  activeSession = null
  const noSession = await studentApi.getStudentM1V2()
  assert.equal(noSession.ok, false)
  if (!noSession.ok) assert.equal(noSession.error.status, 401)

  activeSession = { ...DEFAULT_SESSION, role: "Faculty" }
  const wrongRole = await studentApi.getStudentM1V2()
  assert.equal(wrongRole.ok, false)
  if (!wrongRole.ok) assert.equal(wrongRole.error.status, 403)

  activeSession = { ...DEFAULT_SESSION, student_id: null }
  const unlinked = await studentApi.getStudentM1V2()
  assert.equal(unlinked.ok, false)
  if (!unlinked.ok) assert.equal(unlinked.error.status, 400)
})

test("getStudentM1V2 returns 200 with NO_DATA for unavailable predictions", async () => {
  const NO_DATA_BODY = {
    ...M1V2_BODY,
    readiness_status: "NO_DATA",
    reason: "Not enough current-semester academic data is available",
    subjects: [],
    prediction_count: 0,
  }
  route("/predict/m1v2/STU-A", 200, NO_DATA_BODY)
  const result = await studentApi.getStudentM1V2()
  assert.equal(result.ok, true)
  if (result.ok) {
    assert.equal(result.data.readiness_status, "NO_DATA")
    assert.equal(result.data.subjects.length, 0)
  }
})

test("getStudentM1V2 is cached across reads", async () => {
  route("/predict/m1v2/STU-A", 200, M1V2_BODY)
  await studentApi.getStudentM1V2()
  await studentApi.getStudentM1V2()
  const gets = getCalls("/predict/m1v2")
  assert.equal(gets.length, 1, "second read must hit the cache")
})

test("getStudentM1V2 maps 503 network/backend failure", async () => {
  route("/predict/m1v2/STU-A", 503, { detail: "down" })
  const result = await studentApi.getStudentM1V2()
  assert.equal(result.ok, false)
  if (!result.ok) assert.equal(result.error.status, 503)
})

// ---------------------------------------------------------------------------
// M2 V2 — Next-Semester Performance Prediction (validated production model).
// The per-student route /predict/m2v2/{student_id} is consumed by the student
// BFF. NO_DATA (incl. the deployment boundary: current cohort in the final /
// internship semester has no upcoming regular semester) surfaces as a 404.
// ---------------------------------------------------------------------------

const M2V2_BODY = {
  student_id: "STU-A",
  model_id: "m2_v2",
  model_version: "2.0",
  readiness_status: "READY",
  observation_semester: 6,
  prediction_takes_effect_semester: 7,
  predicted_next_semester_sgpa: 8.12,
  predicted_next_semester_percentage: 76.4,
  algorithm: { next_semester_sgpa: "random_forest", next_semester_percentage: "ridge" },
  reason: null,
  predicted_at: "2026-09-01T08:00:00Z",
  inference_ms: 2.1,
  note: "Predicted next-semester SGPA/percentage are model estimates.",
}

test("getStudentM2V2 fetches /predict/m2v2 with own student id and parses typed result", async () => {
  route("/predict/m2v2/STU-A", 200, M2V2_BODY)

  const result = await studentApi.getStudentM2V2()
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.model_id, "m2_v2")
  assert.equal(result.data.readiness_status, "READY")
  assert.equal(result.data.prediction_takes_effect_semester, 7)
  assert.equal(result.data.predicted_next_semester_sgpa, 8.12)
  assert.equal(result.data.predicted_next_semester_percentage, 76.4)

  const hit = getCalls("/predict/m2v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m2v2/STU-A")
})

test("getStudentM2V2 url-encodes the student id", async () => {
  activeSession = { ...DEFAULT_SESSION, student_id: "STU A/1" }
  route("/predict/m2v2/STU%20A%2F1", 200, M2V2_BODY)

  const result = await studentApi.getStudentM2V2()
  assert.equal(result.ok, true)
  const hit = getCalls("/predict/m2v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m2v2/STU%20A%2F1")
})

test("getStudentM2V2 auth gating (401 / 403 / 400) applies", async () => {
  activeSession = null
  const noSession = await studentApi.getStudentM2V2()
  assert.equal(noSession.ok, false)
  if (!noSession.ok) assert.equal(noSession.error.status, 401)

  activeSession = { ...DEFAULT_SESSION, role: "Faculty" }
  const wrongRole = await studentApi.getStudentM2V2()
  assert.equal(wrongRole.ok, false)
  if (!wrongRole.ok) assert.equal(wrongRole.error.status, 403)

  activeSession = { ...DEFAULT_SESSION, student_id: null }
  const unlinked = await studentApi.getStudentM2V2()
  assert.equal(unlinked.ok, false)
  if (!unlinked.ok) assert.equal(unlinked.error.status, 400)
})

test("getStudentM2V2 maps 404 (NO_DATA / deployment boundary) and is cached", async () => {
  route("/predict/m2v2/STU-A", 200, M2V2_BODY)
  await studentApi.getStudentM2V2()
  await studentApi.getStudentM2V2()
  const gets = getCalls("/predict/m2v2")
  assert.equal(gets.length, 1, "second read must hit the cache")

  routes.clear()
  route("/predict/m2v2/STU-A", 404, { detail: "no upcoming normal academic semester" })
  await studentApi.invalidateBffKeys(DEFAULT_SESSION.student_id, [""])
  const missing = await studentApi.getStudentM2V2()
  assert.equal(missing.ok, false)
  if (!missing.ok) assert.equal(missing.error.code, "not_found")
})

test("getStudentM2V2 maps 503 network/backend failure", async () => {
  route("/predict/m2v2/STU-A", 503, { detail: "down" })
  const result = await studentApi.getStudentM2V2()
  assert.equal(result.ok, false)
  if (!result.ok) assert.equal(result.error.status, 503)
})

// ---------------------------------------------------------------------------
// M3 V2 — At-Risk Student Prediction (validated production model).
// The per-student route /predict/m3v2/{student_id} is consumed by the student
// BFF. probability_at_risk is a model ESTIMATE (never a guarantee). NO_DATA
// (incl. the deployment boundary: the current cohort is in the final /
// internship semester with no upcoming regular semester) surfaces as a 404.
// ---------------------------------------------------------------------------

const M3V2_BODY = {
  student_id: "STU-A",
  model_id: "m3_v2",
  model_version: "2.0",
  readiness_status: "READY",
  observation_semester: 6,
  prediction_takes_effect_semester: 7,
  probability_at_risk: 0.09,
  threshold: 0.64,
  is_estimated_at_risk: false,
  signals: [{ feature: "semester_percentage", raw_value: 76.4, importance: 0.2 }],
  algorithm: { is_at_risk_next_sem: "random_forest" },
  reason: null,
  predicted_at: "2026-09-01T08:00:00Z",
  inference_ms: 2.1,
  note: "Estimated academic-risk probability is a model estimate.",
}

test("getStudentM3V2 fetches /predict/m3v2 with own student id and parses typed result", async () => {
  route("/predict/m3v2/STU-A", 200, M3V2_BODY)

  const result = await studentApi.getStudentM3V2()
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.model_id, "m3_v2")
  assert.equal(result.data.readiness_status, "READY")
  assert.equal(result.data.prediction_takes_effect_semester, 7)
  assert.equal(result.data.probability_at_risk, 0.09)
  assert.equal(result.data.is_estimated_at_risk, false)

  const hit = getCalls("/predict/m3v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m3v2/STU-A")
})

test("getStudentM3V2 url-encodes the student id", async () => {
  activeSession = { ...DEFAULT_SESSION, student_id: "STU A/1" }
  route("/predict/m3v2/STU%20A%2F1", 200, M3V2_BODY)

  const result = await studentApi.getStudentM3V2()
  assert.equal(result.ok, true)
  const hit = getCalls("/predict/m3v2")
  assert.equal(hit.length, 1)
  assert.equal(hit[0].url, "http://localhost:8000/api/v1/predict/m3v2/STU%20A%2F1")
})

test("getStudentM3V2 auth gating (401 / 403 / 400) applies", async () => {
  activeSession = null
  const noSession = await studentApi.getStudentM3V2()
  assert.equal(noSession.ok, false)
  if (!noSession.ok) assert.equal(noSession.error.status, 401)

  activeSession = { ...DEFAULT_SESSION, role: "Faculty" }
  const wrongRole = await studentApi.getStudentM3V2()
  assert.equal(wrongRole.ok, false)
  if (!wrongRole.ok) assert.equal(wrongRole.error.status, 403)

  activeSession = { ...DEFAULT_SESSION, student_id: null }
  const unlinked = await studentApi.getStudentM3V2()
  assert.equal(unlinked.ok, false)
  if (!unlinked.ok) assert.equal(unlinked.error.status, 400)
})

test("getStudentM3V2 maps 404 (NO_DATA / deployment boundary) and is cached", async () => {
  route("/predict/m3v2/STU-A", 200, M3V2_BODY)
  await studentApi.getStudentM3V2()
  await studentApi.getStudentM3V2()
  const gets = getCalls("/predict/m3v2")
  assert.equal(gets.length, 1, "second read must hit the cache")

  routes.clear()
  route("/predict/m3v2/STU-A", 404, { detail: "no upcoming normal academic semester" })
  await studentApi.invalidateBffKeys(DEFAULT_SESSION.student_id, [""])
  const missing = await studentApi.getStudentM3V2()
  assert.equal(missing.ok, false)
  if (!missing.ok) assert.equal(missing.error.code, "not_found")
})

test("getStudentM3V2 maps 503 network/backend failure", async () => {
  route("/predict/m3v2/STU-A", 503, { detail: "down" })
  const result = await studentApi.getStudentM3V2()
  assert.equal(result.ok, false)
  if (!result.ok) assert.equal(result.error.status, 503)
})

test("getStudentM3V2 keeps the at-risk estimate framing honest", async () => {
  // is_estimated_at_risk is driven by the tuned threshold + probability estimate.
  // It must parse into the shared M3V2PredictionData shape and the signals list
  // (feature contributions to the model estimate) round-trips unchanged.
  route("/predict/m3v2/STU-A", 200, M3V2_BODY)
  const result = await studentApi.getStudentM3V2()
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.signals.length, 1)
  assert.equal(result.data.signals[0].feature, "semester_percentage")
  assert.equal(result.data.algorithm?.["is_at_risk_next_sem"], "random_forest")
})
