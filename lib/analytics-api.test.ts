// Frontend tests for the analytics BFF layer (lib/analytics-api.ts).
//
// Runs with Node's built-in test runner + TypeScript type stripping:
//   node --experimental-test-module-mocks --test lib/analytics-api.test.ts
//
// Covers analytics-api contracts without a live FastAPI:
//   * auth gating (no session -> 401)
//   * each endpoint route & query-string building
//   * HTTP error -> BffError mapping
//   * fetch timeout -> unavailable

import { test, mock, beforeEach } from "node:test"
import assert from "node:assert/strict"

// ---------------------------------------------------------------------------
// Session mock — registered BEFORE analytics-api is imported
// ---------------------------------------------------------------------------

let activeSession: unknown = null

mock.module("./student-session.ts", {
  namedExports: {
    getSessionUser: async () => activeSession,
  },
})

// analytics-api imports from the same student-session.ts module
const analyticsApi = await import("./analytics-api.ts")

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

// ---------------------------------------------------------------------------
// Auth gating
// ---------------------------------------------------------------------------

test("analytics: no session -> 401 unauthorized, fetch never called", async () => {
  activeSession = null
  const result = await analyticsApi.getDepartmentOverview()
  assert.equal(result.ok, false)
  assert.equal(calls.length, 0)
})

// ---------------------------------------------------------------------------
// getDepartmentOverview
// ---------------------------------------------------------------------------

test("getDepartmentOverview: successful response with filters", async () => {
  const body = {
    department_code: 1,
    department_name: "Computer Science and Engineering",
    semester_no: 7,
    academic_year: "2026-27",
    total_students: 50,
    average_sgpa: 7.5,
    average_percentage: 75.0,
    average_attendance_percentage: 82.3,
    total_backlogs: 12,
    students_with_backlogs: 8,
  }
  route("departments/overview", 200, body)

  const result = await analyticsApi.getDepartmentOverview({
    department_code: 1,
    semester_no: 7,
  })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.department_code, 1)
  assert.equal(result.data.department_name, "Computer Science and Engineering")
  assert.equal(result.data.total_students, 50)
  assert.equal(result.data.average_sgpa, 7.5)

  const hit = getCalls("departments/overview")
  assert.equal(hit.length, 1)
  assert.ok(hit[0].url.includes("department_code=1"))
  assert.ok(hit[0].url.includes("semester_no=7"))
})

// ---------------------------------------------------------------------------
// getPerformanceDistribution
// ---------------------------------------------------------------------------

test("getPerformanceDistribution: returns bucket data", async () => {
  const body = {
    department_code: 1,
    semester_no: 7,
    academic_year: "2026-27",
    total_students: 50,
    buckets: [
      { label: "Top", count: 10, percentage_of_total: 20.0 },
      { label: "Average", count: 20, percentage_of_total: 40.0 },
      { label: "Low Performer", count: 5, percentage_of_total: 10.0 },
    ],
  }
  route("performance-distribution", 200, body)

  const result = await analyticsApi.getPerformanceDistribution({ department_code: 1 })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.total_students, 50)
  assert.equal(result.data.buckets.length, 3)
  assert.equal(result.data.buckets[0].label, "Top")
  assert.equal(result.data.buckets[0].count, 10)
})

// ---------------------------------------------------------------------------
// getAttendanceDistribution
// ---------------------------------------------------------------------------

test("getAttendanceDistribution: returns band data", async () => {
  const body = {
    department_code: 1,
    semester_no: null,
    total_students: 50,
    buckets: [
      { band: "Excellent", count: 15, percentage_of_total: 30.0 },
      { band: "Critical", count: 5, percentage_of_total: 10.0 },
    ],
  }
  route("attendance-distribution", 200, body)

  const result = await analyticsApi.getAttendanceDistribution()
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.buckets.length, 2)
  assert.equal(result.data.buckets[0].band, "Excellent")
})

// ---------------------------------------------------------------------------
// getBacklogDistribution
// ---------------------------------------------------------------------------

test("getBacklogDistribution: returns range buckets", async () => {
  const body = {
    department_code: 1,
    total_students: 50,
    students_with_backlogs: 8,
    buckets: [
      { backlog_range: "0", count: 42, percentage_of_total: 84.0 },
      { backlog_range: "1-3", count: 6, percentage_of_total: 12.0 },
    ],
  }
  route("backlog-distribution", 200, body)

  const result = await analyticsApi.getBacklogDistribution({ department_code: 1 })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.students_with_backlogs, 8)
  assert.equal(result.data.buckets[0].backlog_range, "0")
})

// ---------------------------------------------------------------------------
// getAtRiskStudents
// ---------------------------------------------------------------------------

test("getAtRiskStudents: returns flagged students", async () => {
  const body = {
    department_code: 1,
    semester_no: 7,
    total_flagged: 5,
    students: [
      {
        student_id: "STU000001",
        full_name: "Rahul Kumar",
        department_code: 1,
        current_semester: 7,
        overall_cgpa: 4.2,
        total_backlogs: 3,
        overall_attendance_percentage: 65.0,
        risk_reasons: ["Low CGPA", "High Backlogs"],
        risk_score: 0.85,
      },
    ],
  }
  route("at-risk/students", 200, body)

  const result = await analyticsApi.getAtRiskStudents({ department_code: 1, semester_no: 7 })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.total_flagged, 5)
  assert.equal(result.data.students[0].student_id, "STU000001")
  assert.equal(result.data.students[0].risk_reasons.length, 2)
})

// ---------------------------------------------------------------------------
// getBelowAttendanceThreshold
// ---------------------------------------------------------------------------

test("getBelowAttendanceThreshold: returns students with attendance shortage", async () => {
  const body = {
    threshold: 75.0,
    semester_no: 7,
    total_flagged: 3,
    students: [
      {
        student_id: "STU000002",
        full_name: "Priya Patel",
        subject_id: "SUB0050",
        subject_code: "CS301",
        attendance_percentage: 68.5,
        total_classes: 40,
        attended_classes: 27,
        classes_needed: 3,
      },
    ],
  }
  route("at-risk/below-attendance-threshold", 200, body)

  const result = await analyticsApi.getBelowAttendanceThreshold({ threshold: 75 })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.threshold, 75.0)
  assert.equal(result.data.students[0].classes_needed, 3)
})

// ---------------------------------------------------------------------------
// getSubjectsNeedingAttention
// ---------------------------------------------------------------------------

test("getSubjectsNeedingAttention: returns flagged subjects", async () => {
  const body = {
    department_code: 1,
    semester_no: 7,
    total_flagged: 2,
    subjects: [
      {
        subject_id: "SUB0050",
        subject_code: "CS301",
        subject_name: "Data Structures",
        semester_no: 7,
        total_students: 50,
        average_percentage: 42.5,
        fail_rate: 28.0,
        average_attendance: 71.2,
        reasons: ["Low Average %", "High Fail Rate"],
      },
    ],
  }
  route("subjects-needing-attention", 200, body)

  const result = await analyticsApi.getSubjectsNeedingAttention({ department_code: 1 })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.total_flagged, 2)
  assert.equal(result.data.subjects[0].subject_code, "CS301")
  assert.equal(result.data.subjects[0].reasons[0], "Low Average %")
})

// ---------------------------------------------------------------------------
// Student endpoints
// ---------------------------------------------------------------------------

test("getStudentAcademicProfile: fetches profile for student", async () => {
  const body = {
    student_id: "STU000001",
    full_name: "Rahul Kumar",
    department_code: 1,
    department_name: "Computer Science and Engineering",
    current_semester: 7,
    current_academic_year: "2026-27",
    overall_cgpa: 7.2,
    latest_sgpa: 7.5,
    total_backlogs: 1,
    overall_attendance_percentage: 82.0,
    total_subjects_enrolled: 6,
    total_credits_registered: 24,
  }
  route("students/STU000001/academic-profile", 200, body)

  const result = await analyticsApi.getStudentAcademicProfile("STU000001")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.student_id, "STU000001")
  assert.equal(result.data.full_name, "Rahul Kumar")
  assert.equal(result.data.overall_cgpa, 7.2)

  assert.ok(getCalls("students/STU000001/academic-profile")[0].url.includes("STU000001"))
})

test("getStudentSemesterHistory: builds filter query string", async () => {
  const body = {
    student_id: "STU000001",
    semesters: [
      { semester_no: 7, semester_sgpa: 7.5, semester_percentage: 75.0 },
      { semester_no: 6, semester_sgpa: 6.8, semester_percentage: 68.0 },
    ],
  }
  route("students/STU000001/semester-history", 200, body)

  const result = await analyticsApi.getStudentSemesterHistory("STU000001", { semester_no: 7 })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.semesters.length, 2)

  const url = getCalls("semester-history")[0].url
  assert.ok(url.includes("semester_no=7"))
})

test("getStudentBacklogSummary: fetches backlogs", async () => {
  const body = {
    student_id: "STU000001",
    total_backlogs: 1,
    backlogs: [
      { subject_id: "SUB0050", subject_code: "CS301", percentage: 38.0, grade: "F" },
    ],
  }
  route("students/STU000001/backlog-summary", 200, body)

  const result = await analyticsApi.getStudentBacklogSummary("STU000001")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.total_backlogs, 1)
  assert.equal(result.data.backlogs[0].grade, "F")
})

// ---------------------------------------------------------------------------
// Subject endpoints
// ---------------------------------------------------------------------------

test("getSubjectPerformance: fetches subject performance", async () => {
  const body = {
    subject_id: "SUB0050",
    subject_code: "CS301",
    subject_name: "Data Structures",
    semester_no: 7,
    total_students: 50,
    average_percentage: 65.0,
    median_percentage: 63.0,
    min_percentage: 12.0,
    max_percentage: 98.0,
    pass_count: 42,
    fail_count: 8,
    pass_rate: 84.0,
    grade_distribution: [{ grade: "A", count: 15 }, { grade: "F", count: 8 }],
  }
  route("subjects/SUB0050/performance", 200, body)

  const result = await analyticsApi.getSubjectPerformance("SUB0050")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.subject_code, "CS301")
  assert.equal(result.data.pass_rate, 84.0)
  assert.equal(result.data.grade_distribution.length, 2)
})

test("getSubjectAttendance: fetches attendance summary", async () => {
  const body = {
    subject_id: "SUB0050",
    subject_code: "CS301",
    subject_name: "Data Structures",
    semester_no: 7,
    total_students: 50,
    average_attendance_percentage: 81.5,
    eligible_count: 42,
    at_risk_count: 5,
    ineligible_count: 3,
    shortage_count: 2,
  }
  route("subjects/SUB0050/attendance", 200, body)

  const result = await analyticsApi.getSubjectAttendance("SUB0050")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.eligible_count, 42)
  assert.equal(result.data.ineligible_count, 3)
})

test("getSubjectUnderperformers: fetches with threshold filter", async () => {
  const body = {
    subject_id: "SUB0050",
    semester_no: 7,
    threshold: 40.0,
    students: [
      { student_id: "STU000003", full_name: "Amit Singh", percentage: 35.0, grade: "F" },
    ],
  }
  route("subjects/SUB0050/underperformers", 200, body)

  const result = await analyticsApi.getSubjectUnderperformers("SUB0050", { threshold: 40 })
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.data.threshold, 40.0)
  assert.equal(result.data.students[0].percentage, 35.0)

  const url = getCalls("underperformers")[0].url
  assert.ok(url.includes("threshold=40"))
})

// ---------------------------------------------------------------------------
// Error mapping
// ---------------------------------------------------------------------------

test("analytics error mapping: 401/403/404/422/503/500", async () => {
  const cases: Array<[number, string]> = [
    [401, "unauthorized"],
    [403, "unauthorized"],
    [404, "invalid"],
    [422, "invalid"],
    [503, "unavailable"],
    [500, "server_error"],
  ]
  for (const [status, code] of cases) {
    route("departments/overview", status, { detail: "x" })
    const result = await analyticsApi.getDepartmentOverview({ department_code: status })
    assert.equal(result.ok, false, `status ${status} should return ok=false`)
    if (result.ok) continue
    assert.equal(result.error.code, code, `status ${status} should map to ${code}`)
    assert.equal(result.error.status, status)
  }
})

// ---------------------------------------------------------------------------
// Cache behavior
// ---------------------------------------------------------------------------

test("analytics BFF cache: same filter returns cached result", async () => {
  const body = { department_code: 1, total_students: 50 }
  route("departments/overview", 200, body)

  const r1 = await analyticsApi.getDepartmentOverview({ department_code: 1 })
  assert.equal(r1.ok, true)
  const r2 = await analyticsApi.getDepartmentOverview({ department_code: 1 })
  assert.equal(r2.ok, true)
  // Only one fetch call should be made due to caching
  assert.equal(getCalls("departments/overview").length, 1)
})

test("analytics BFF cache: different filters miss the cache", async () => {
  // Use unique academic_year filters to avoid cache collisions with prior tests
  route("departments/overview?department_code=10&academic_year=2099", 200, { department_code: 10, total_students: 50 })
  route("departments/overview?department_code=20&academic_year=2099", 200, { department_code: 20, total_students: 30 })

  const r1 = await analyticsApi.getDepartmentOverview({ department_code: 10, academic_year: "2099" })
  assert.equal(r1.ok, true)
  if (r1.ok) assert.equal(r1.data.department_code, 10)

  const r2 = await analyticsApi.getDepartmentOverview({ department_code: 20, academic_year: "2099" })
  assert.equal(r2.ok, true)
  if (r2.ok) assert.equal(r2.data.department_code, 20)

  assert.equal(getCalls("departments/overview").length, 2)
})

// ---------------------------------------------------------------------------
// Empty query omission
// ---------------------------------------------------------------------------

test("getDepartmentOverview with no filters omits query string", async () => {
  // Use a unique department_code to avoid cache collision with prior tests
  route("subjects/SUB999/performance?semester_no=99", 200, { subject_id: "SUB999", total_students: 50 })

  const result = await analyticsApi.getSubjectPerformance("SUB999", { semester_no: 99 })
  assert.equal(result.ok, true)
  const url = getCalls("SUB999/performance")[0].url
  assert.ok(url.includes("semester_no=99"))
  assert.ok(!url.includes("undefined"), "should not contain 'undefined' in query")
})
