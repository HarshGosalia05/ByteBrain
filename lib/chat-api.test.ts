import { test, mock, beforeEach } from "node:test"
import assert from "node:assert/strict"

interface MockSession {
  role: string
  user_id?: string
  student_id?: string
  faculty_id?: string
}

let mockSession: MockSession | null = {
  role: "Student",
  user_id: "STU000001",
  student_id: "STU000001",
}

mock.module("./student-session.ts", {
  namedExports: {
    getSessionUser: async () => mockSession,
    getSessionToken: async () => "mock.jwt.token",
  },
})

// Import after registering mock so next/headers is never loaded
const { sendChatMessage, fetchPortalContext, toChatBffError } = await import("./chat-api.ts")

interface FetchCall {
  url: string
  options?: RequestInit
}

const calls: FetchCall[] = []
const routes = new Map<string, { status?: number; body?: unknown }>()
const defaultStatus = 200
const defaultBody: unknown = {
  message: "Here is your academic overview: SGPA is 8.5.",
  intent: "academic_performance",
  tool_name: "student_academic_tool",
  status: "success",
  verified_sources: ["student_academic_performance_source"],
  provider: "openai_compatible",
  model: "gpt-4o-mini",
  generated_at: "2026-08-14T10:00:00Z",
}

globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof input === "string" ? input : input.toString()
  calls.push({ url, options: init })

  for (const [pattern, fixture] of routes.entries()) {
    if (url.includes(pattern)) {
      const status = fixture.status ?? 200
      return new Response(JSON.stringify(fixture.body ?? {}), {
        status,
        headers: { "Content-Type": "application/json" },
      })
    }
  }

  return new Response(JSON.stringify(defaultBody), {
    status: defaultStatus,
    headers: { "Content-Type": "application/json" },
  })
}

beforeEach(() => {
  calls.length = 0
  routes.clear()
  mockSession = { role: "Student", student_id: "STU000001", user_id: "STU000001" }
})

test("no session -> 401 unauthorized, fetch never called", async () => {
  mockSession = null
  const result = await sendChatMessage({ message: "Hello" })
  assert.equal(result.success, false)
  if (!result.success) {
    assert.equal(result.error.status, 401)
    assert.equal(result.error.code, "UNAUTHORIZED")
  }
  assert.equal(calls.length, 0)
})

test("empty or whitespace-only message -> 422 invalid, fetch never called", async () => {
  const result = await sendChatMessage({ message: "   " })
  assert.equal(result.success, false)
  if (!result.success) {
    assert.equal(result.error.status, 422)
    assert.equal(result.error.code, "VALIDATION_ERROR")
  }
  assert.equal(calls.length, 0)
})

test("sendChatMessage forwards a known page_context and drops an unknown one", async () => {
  mockSession = { role: "Student", student_id: "STU000001", user_id: "STU000001" }

  // Valid known page context is forwarded
  await sendChatMessage({ message: "why is this low?", page_context: "student_attendance" })
  let call = calls[0]
  let body = JSON.parse(String(call.options?.body))
  assert.equal(body.page_context, "student_attendance")

  calls.length = 0
  // An unknown/injected arbitrary value is dropped (never forwarded). Note the
  // backend additionally role-scopes known values, since a known value from
  // another role (e.g. student_attendance vs admin_analytics) is still rejected
  // server-side.
  await sendChatMessage({ message: "why is this low?", page_context: "../../etc/passwd" })
  call = calls[0]
  body = JSON.parse(String(call.options?.body))
  assert.equal(body.page_context, undefined)
})

test("sendChatMessage sends sanitized payload with bearer token and returns ChatApiResponse", async () => {
  const result = await sendChatMessage({
    message: "What is my SGPA?",
    intent: "academic_performance",
  })
  assert.equal(result.success, true)
  if (result.success) {
    assert.equal(result.data.status, "success")
    assert.equal(result.data.intent, "academic_performance")
    assert.equal(result.data.message, "Here is your academic overview: SGPA is 8.5.")
  }
  assert.equal(calls.length, 1)
  const call = calls[0]
  assert.ok(call.url.endsWith("/api/v1/chat"))
  const headers = call.options?.headers as Record<string, string>
  assert.ok(headers.Authorization.startsWith("Bearer "))
  const body = JSON.parse(String(call.options?.body))
  assert.equal(body.message, "What is my SGPA?")
  assert.equal(body.intent, "academic_performance")
})

test("sendChatMessage limits conversation_history to last 10 messages", async () => {
  const history = Array.from({ length: 15 }, (_, i) => ({
    role: (i % 2 === 0 ? "user" : "assistant") as "user" | "assistant",
    content: `Message ${i + 1}`,
  }))

  const result = await sendChatMessage({
    message: "Latest follow up",
    conversation_history: history,
  })
  assert.equal(result.success, true)
  const call = calls[0]
  const body = JSON.parse(String(call.options?.body))
  assert.equal(body.conversation_history.length, 10)
  assert.equal(body.conversation_history[0].content, "Message 6")
  assert.equal(body.conversation_history[9].content, "Message 15")
})

test("error mapping: 401 unauthorized, 403 forbidden, 429 rate limited, 503 unavailable, 504 gateway timeout, 500 server error", async () => {
  const errorCodes = [
    { status: 401, code: "UNAUTHORIZED" },
    { status: 403, code: "FORBIDDEN" },
    { status: 429, code: "RATE_LIMITED" },
    { status: 503, code: "SERVICE_UNAVAILABLE" },
    { status: 504, code: "GATEWAY_TIMEOUT" },
    { status: 500, code: "SERVER_ERROR" },
  ]

  for (const { status, code } of errorCodes) {
    routes.clear()
    routes.set("/api/v1/chat", {
      status,
      body: { detail: `Error detail for ${status}` },
    })
    const result = await sendChatMessage({ message: "Test query" })
    assert.equal(result.success, false)
    if (!result.success) {
      assert.equal(result.error.status, status)
      assert.equal(result.error.code, code)
      assert.ok(result.error.message.length > 0)
    }
  }
})

test("toChatBffError returns standardized safe messages", () => {
  const err401 = toChatBffError(401)
  assert.equal(err401.code, "UNAUTHORIZED")
  const err429 = toChatBffError(429)
  assert.equal(err429.code, "RATE_LIMITED")
  const err503 = toChatBffError(503)
  assert.equal(err503.code, "SERVICE_UNAVAILABLE")
  const err504 = toChatBffError(504)
  assert.equal(err504.code, "GATEWAY_TIMEOUT")
})

test("fetchPortalContext hits /api/v1/chat/context with bearer token and returns data", async () => {
  const ctxBody = {
    role: "Student",
    student: {
      name: "Aarav Sharma",
      cgpa: 8.2,
      overall_attendance: 92,
      top_subjects: [{ name: "Data Structures", percentage: 89 }],
    },
    generated_at: "2026-08-14T11:00:00Z",
    data_available: true,
  }
  routes.set("/api/v1/chat/context", { body: ctxBody })

  const result = await fetchPortalContext()
  assert.equal(result.success, true)
  if (result.success) {
    assert.equal(result.data.role, "Student")
    assert.equal(result.data.student?.cgpa, 8.2)
    assert.equal(result.data.data_available, true)
  }
  const call = calls[0]
  assert.ok(call.url.endsWith("/api/v1/chat/context"))
  const headers = call.options?.headers as Record<string, string>
  assert.ok(headers.Authorization.startsWith("Bearer "))
})

test("fetchPortalContext no session -> 401 unauthorized, fetch never called", async () => {
  mockSession = null
  const result = await fetchPortalContext()
  assert.equal(result.success, false)
  if (!result.success) {
    assert.equal(result.error.status, 401)
    assert.equal(result.error.code, "UNAUTHORIZED")
  }
  assert.equal(calls.length, 0)
})

test("fetchPortalContext backend 503 -> SERVICE_UNAVAILABLE with safe message", async () => {
  routes.set("/api/v1/chat/context", { status: 503, body: { detail: "backend down" } })
  const result = await fetchPortalContext()
  assert.equal(result.success, false)
  if (!result.success) {
    assert.equal(result.error.status, 503)
    assert.equal(result.error.code, "SERVICE_UNAVAILABLE")
  }
})
