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

