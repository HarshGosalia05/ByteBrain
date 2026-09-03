// Frontend tests for the MD-06 career guidance BFF layer (lib/student-api.ts).
//
// Runs with Node's built-in test runner + TypeScript type stripping:
//   node --experimental-test-module-mocks --test lib/student/career-guidance-api.test.ts
//
// Covers the career guidance contract without a live FastAPI:
//   * auth gating (401 no session / 403 wrong role / 400 unlinked)
//   * GET /students/me/career/guidance wiring + bearer token
//   * response passthrough for the guidance card payload
//   * graceful error mapping (503/404) so the UI can degrade to
//     deterministic-only rendering
//   * 60s BFF cache hit behaviour

import { test, mock, beforeEach } from "node:test"
import assert from "node:assert/strict"

let activeSession: unknown = null

mock.module("../student-session.ts", {
  namedExports: {
    getSessionUser: async () => activeSession,
    getSessionToken: async () => (activeSession ? "mock.signed.jwt.token" : null),
  },
})

const studentApi = await import("../student-api.ts")

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

const GUIDANCE_PAYLOAD = {
  student_id: "STU-A",
  data_available: true,
  career_preferences_available: true,
  career_readiness: {
    available: true,
    score: 72.5,
    level: "Good",
    positive_factors: ["Strong academics"],
    risk_factors: ["Low attendance"],
    disclaimer: "M4 is a deterministic rule-based career-readiness score.",
  },
  career_direction: {
    available: true,
    domain: "Data Science",
    source: "declared_preference",
    matched_count: 3,
    note: "3 of your completed subjects map to Data Science.",
  },
  skill_strengths: [
    {
      skill: "Machine Learning concepts",
      evidence: "inferred_from_subject",
      source_subject: "Machine Learning",
      detail: "Inferred from Machine Learning at 75.0%.",
    },
  ],
  skill_gaps: [
    {
      rank: 1,
      skill_area: "statistics",
      priority: "High",
      detail: "No verified subject evidence for 'statistics'.",
      evidence: "not_verified",
    },
  ],
  roadmap: [],
  ai_guidance: {
    available: false,
    content: null,
    provider: null,
    model: null,
    error: "unavailable",
  },
  source: "students/career_coach",
  generated_at: "2026-08-23T00:00:00Z",
}

// ---------------------------------------------------------------------------
// Auth gating
// ---------------------------------------------------------------------------

test("no session -> 401 unauthorized, fetch never called", async () => {
  activeSession = null
  const result = await studentApi.getStudentCareerGuidance()
  assert.equal(result.ok, false)
  if (!result.ok) assert.equal(result.error.code, "unauthorized")
  assert.equal(calls.length, 0)
})

test("non-student role -> 403 unauthorized", async () => {
  activeSession = { ...DEFAULT_SESSION, role: "Faculty" }
  const result = await studentApi.getStudentCareerGuidance()
  assert.equal(result.ok, false)
  if (!result.ok) assert.equal(result.error.status, 403)
  assert.equal(calls.length, 0)
})

test("session without linked student record -> 400 unlinked", async () => {
  activeSession = { ...DEFAULT_SESSION, student_id: undefined }
  const result = await studentApi.getStudentCareerGuidance()
  assert.equal(result.ok, false)
  if (!result.ok) assert.equal(result.error.code, "unlinked")
})

// ---------------------------------------------------------------------------
// Request + response wiring
// ---------------------------------------------------------------------------

test("GETs own career/guidance with bearer token", async () => {
  defaultBody = GUIDANCE_PAYLOAD
  const result = await studentApi.getStudentCareerGuidance()
  assert.equal(result.ok, true)
  assert.equal(calls.length, 1)

  const call = calls[0]
  assert.ok(call.url.includes("/api/v1/students/me/career/guidance"))
  const headers = call.init?.headers as Record<string, string>
  assert.ok(headers.Authorization?.startsWith("Bearer "))

  if (result.ok) {
    assert.equal(result.data.student_id, "STU-A")
    assert.equal(result.data.career_direction.domain, "Data Science")
    assert.equal(result.data.career_direction.source, "declared_preference")
    assert.equal(result.data.career_readiness.score, 72.5)
    assert.equal(result.data.skill_gaps[0].priority, "High")
    assert.equal(result.data.ai_guidance.available, false)
  }
})

test("payload is scoped to the authenticated student id in the cache key", async () => {
  defaultBody = GUIDANCE_PAYLOAD
  await studentApi.getStudentCareerGuidance()
  activeSession = { ...DEFAULT_SESSION, student_id: "STU-B" }
  studentApi.invalidateBffKeys(DEFAULT_SESSION.student_id, [""])
  calls.length = 0
  defaultBody = { ...GUIDANCE_PAYLOAD, student_id: "STU-B" }
  const result = await studentApi.getStudentCareerGuidance()
  if (result.ok) {
    assert.equal(result.data.student_id, "STU-B")
  }
  assert.ok(calls[0]?.url.includes("career/guidance"))
})

// ---------------------------------------------------------------------------
// Error mapping / degradation
// ---------------------------------------------------------------------------

test("backend 503 -> unavailable error the UI can degrade on", async () => {
  route("career/guidance", 503, {})
  const result = await studentApi.getStudentCareerGuidance()
  assert.equal(result.ok, false)
  if (!result.ok) {
    assert.equal(result.error.code, "unavailable")
    assert.equal(result.error.status, 503)
  }
})

test("backend 404 -> not_found", async () => {
  route("career/guidance", 404, {})
  const result = await studentApi.getStudentCareerGuidance()
  assert.equal(result.ok, false)
  if (!result.ok) assert.equal(result.error.code, "not_found")
})

test("network failure -> unavailable error, never throws", async () => {
  globalThis.fetch = (async () => {
    throw new TypeError("fetch failed")
  }) as typeof fetch
  const result = await studentApi.getStudentCareerGuidance()
  assert.equal(result.ok, false)
  if (!result.ok) assert.equal(result.error.code, "unavailable")
})

// ---------------------------------------------------------------------------
// Cache
// ---------------------------------------------------------------------------

test("second call within TTL served from cache without refetch", async () => {
  defaultBody = GUIDANCE_PAYLOAD
  const first = await studentApi.getStudentCareerGuidance()
  calls.length = 0
  const second = await studentApi.getStudentCareerGuidance()
  assert.equal(second.ok, true)
  assert.equal(calls.length, 0)
  if (first.ok && second.ok) {
    assert.deepEqual(second.data, first.data)
  }
})
