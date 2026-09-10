import { getSessionUser, getSessionToken } from "./student-session.ts"
import { PAGE_CONTEXTS } from "./page-context.ts"

const FASTAPI_URL = (process.env.FASTAPI_URL ?? "http://localhost:8000").replace(/\/+$/, "")

export interface ConversationHistoryItem {
  role: "user" | "assistant"
  content: string
}

export interface ChatApiRequest {
  message: string
  intent?: string | null
  target_student_id?: string | null
  page_context?: string | null
  conversation_history?: ConversationHistoryItem[]
}

export interface ChatApiResponse {
  message: string
  intent: string | null
  tool_name: string | null
  status: "success" | "clarification" | "unauthorized" | "unavailable" | "rate_limited"
  verified_sources: string[]
  provider?: string | null
  model?: string | null
  generated_at?: string
}

// --- Portal context (ETL preload) -------------------------------------------

export interface StudentPortalContext {
  name?: string | null
  enrollment_no?: number | null
  department?: string | null
  current_semester?: number | null
  academic_year?: string | null
  cgpa?: number | null
  sgpa?: number | null
  percentage?: number | null
  backlogs?: number | null
  academic_standing?: string | null
  overall_attendance?: number | null
  top_subjects?: { name?: string | null; percentage?: number | null; grade?: string | null }[]
  weak_subjects?: { name?: string | null; percentage?: number | null; grade?: string | null }[]
  prediction_summary?: { available?: boolean; predictions?: { type?: string; status?: string }[] }
  career_readiness?: { available?: boolean; domain?: string | null; dream_role?: string | null }
  upcoming_classes?: { day?: string | null; time?: string | null; subject?: string | null; type?: string | null }[]
  recent_notifications?: { title?: string | null; body?: string | null; priority?: string | null }[]
}

export interface FacultyPortalContext {
  name?: string | null
  department?: string | null
  designation?: string | null
  subjects_taught?: { name?: string | null; code?: string | null; semester?: number | null }[]
  total_mentees?: number | null
  flagged_students?: { id?: string | null; name?: string | null; cgpa?: number | null; backlogs?: number | null; standing?: string | null }[]
  class_summary?: { total_students?: number | null; avg_cgpa?: number | null; avg_attendance?: number | null }
  department_summary?: Record<string, unknown>
}

export interface AdminPortalContext {
  institution_name?: string | null
  total_students?: number | null
  total_faculty?: number | null
  total_departments?: number | null
  overall_cgpa?: number | null
  overall_attendance?: number | null
  flagged_count?: number | null
  department_performance?: { name?: string | null; students?: number | null; avg_cgpa?: number | null; avg_attendance?: number | null }[]
  recent_trends?: Record<string, unknown>[]
}

export interface PortalContextResponse {
  role: "Student" | "Faculty" | "Admin"
  student?: StudentPortalContext | null
  faculty?: FacultyPortalContext | null
  admin?: AdminPortalContext | null
  generated_at?: string
  data_available: boolean
  note?: string | null
}

export interface ChatBffError {
  status: number
  code: string
  message: string
}

export type ChatBffResult =
  | { success: true; data: ChatApiResponse }
  | { success: false; error: ChatBffError }

export function toChatBffError(status: number, message?: string): ChatBffError {
  switch (status) {
    case 401:
      return {
        status: 401,
        code: "UNAUTHORIZED",
        message: message ?? "Session expired. Please log in again.",
      }
    case 403:
      return {
        status: 403,
        code: "FORBIDDEN",
        message: message ?? "You are not authorized to perform this chat action.",
      }
    case 422:
      return {
        status: 422,
        code: "VALIDATION_ERROR",
        message: message ?? "Invalid chat request format or message.",
      }
    case 429:
      return {
        status: 429,
        code: "RATE_LIMITED",
        message: message ?? "Too many requests. Please wait a moment before sending another message.",
      }
    case 503:
      return {
        status: 503,
        code: "SERVICE_UNAVAILABLE",
        message: message ?? "AI Chat service is temporarily unavailable. Please try again later.",
      }
    case 504:
      return {
        status: 504,
        code: "GATEWAY_TIMEOUT",
        message: message ?? "The chat assistant took longer than usual to respond. Please try again in a moment.",
      }
    default:
      return {
        status: status >= 400 && status < 600 ? status : 500,
        code: "SERVER_ERROR",
        message: message ?? "An unexpected error occurred while communicating with the chat assistant.",
      }
  }
}

export async function sendChatMessage(req: ChatApiRequest): Promise<ChatBffResult> {
  const session = await getSessionUser()
  if (!session) {
    return { success: false, error: toChatBffError(401) }
  }

  const token = await getSessionToken()
  if (!token) {
    return { success: false, error: toChatBffError(401) }
  }

  const message = req.message?.trim()
  if (!message) {
    return {
      success: false,
      error: toChatBffError(422, "Chat message cannot be empty."),
    }
  }

  // Bounded conversation history (max 10 recent messages)
  const conversation_history = (req.conversation_history ?? [])
    .slice(-10)
    .map((item) => ({
      role: item.role === "assistant" ? "assistant" : "user",
      content: String(item.content ?? "").trim(),
    }))

  const payload: Record<string, unknown> = {
    message,
    conversation_history,
  }

  if (req.intent) {
    payload.intent = req.intent
  }

  // Forward target_student_id for faculty and admin roles
  if ((session.role === "Faculty" || session.role === "Admin") && req.target_student_id) {
    payload.target_student_id = req.target_student_id
  }

  // Forward page_context ONLY if it is a known, allowlisted identifier. The
  // backend re-validates and role-scopes this server-side; it is a context hint,
  // never authorization.
  if (req.page_context && (Object.values(PAGE_CONTEXTS) as string[]).includes(req.page_context)) {
    payload.page_context = req.page_context
  }

  try {
    const res = await fetch(`${FASTAPI_URL}/api/v1/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(30000),
    })

    if (!res.ok) {
      let errorDetail = ""
      try {
        const errJson = await res.json()
        errorDetail = errJson.detail || errJson.message || ""
      } catch {
        // ignore parsing error
      }
      return {
        success: false,
        error: toChatBffError(res.status, errorDetail || undefined),
      }
    }

    const data: ChatApiResponse = await res.json()
    return { success: true, data }
  } catch (err: unknown) {
    const isTimeout = err instanceof Error && (err.name === "TimeoutError" || err.name === "AbortError")
    if (isTimeout) {
      return {
        success: false,
        error: toChatBffError(504, "Chat request timed out. Please try again."),
      }
    }
    const message = err instanceof Error ? err.message : "Network error"
    return {
      success: false,
      error: toChatBffError(503, `Unable to reach chat service: ${message}`),
    }
  }
}

export type FetchPortalContextResult =
  | { success: true; data: PortalContextResponse }
  | { success: false; error: ChatBffError }

export async function fetchPortalContext(): Promise<FetchPortalContextResult> {
  const session = await getSessionUser()
  if (!session) {
    return { success: false, error: toChatBffError(401) }
  }

  const token = await getSessionToken()
  if (!token) {
    return { success: false, error: toChatBffError(401) }
  }

  try {
    const res = await fetch(`${FASTAPI_URL}/api/v1/chat/context`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      signal: AbortSignal.timeout(15000),
    })

    if (!res.ok) {
      let errorDetail = ""
      try {
        const errJson = await res.json()
        errorDetail = errJson.detail || errJson.message || ""
      } catch {
        // ignore parsing error
      }
      return {
        success: false,
        error: toChatBffError(res.status, errorDetail || undefined),
      }
    }

    const data: PortalContextResponse = await res.json()
    return { success: true, data }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error"
    return {
      success: false,
      error: toChatBffError(503, `Unable to load portal context: ${message}`),
    }
  }
}
