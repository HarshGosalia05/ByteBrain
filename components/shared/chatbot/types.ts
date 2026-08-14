export type UserRole = "Student" | "Faculty" | "Admin"

export interface UIMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: string
  status?: "success" | "clarification" | "unauthorized" | "unavailable" | "error"
  intent?: string | null
  toolName?: string | null
  verifiedSources?: string[]
  provider?: string | null
  model?: string | null
  isError?: boolean
}

export interface ChatbotProps {
  role?: UserRole
  targetStudentId?: string | null
  className?: string
}
