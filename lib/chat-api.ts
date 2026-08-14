import { getSessionUser } from "./student-session.ts"

const FASTAPI_URL = (process.env.FASTAPI_URL ?? "http://localhost:8000").replace(/\/+$/, "")

export interface ConversationHistoryItem {
  role: "user" | "assistant"
  content: string
}

export interface ChatApiRequest {
  message: string
  intent?: string | null
  target_student_id?: string | null
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

  const token = Buffer.from(JSON.stringify(session)).toString("base64")

  const payload: Record<string, unknown> = {
    message,
    conversation_history,
  }

  if (req.intent) {
    payload.intent = req.intent
  }

  // Only forward target_student_id if faculty role
  if (session.role === "Faculty" && req.target_student_id) {
    payload.target_student_id = req.target_student_id
  }

  try {
    const res = await fetch(`${FASTAPI_URL}/api/v1/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
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
    const message = err instanceof Error ? err.message : "Network error"
    return {
      success: false,
      error: toChatBffError(503, `Unable to reach chat service: ${message}`),
    }
  }
}
