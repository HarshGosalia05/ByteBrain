"use client"

import * as React from "react"
import { ChatbotLauncher } from "./chatbot-launcher"
import { ChatbotPanel } from "./chatbot-panel"
import { ChatHeader } from "./chat-header"
import { ChatMessageList } from "./chat-message-list"
import { ChatInput } from "./chat-input"
import type { ChatbotProps, PortalSnapshot, UIMessage } from "./types"
import type { ChatApiRequest, PortalContextResponse } from "@/lib/chat-api"

function mapPortalContext(raw: PortalContextResponse | null): PortalSnapshot {
  if (!raw) {
    return { role: "Student", available: false }
  }
  const base: PortalSnapshot = { role: raw.role, available: raw.data_available }

  if (raw.student) {
    base.student = {
      name: raw.student.name,
      department: raw.student.department,
      currentSemester: raw.student.current_semester,
      academicYear: raw.student.academic_year,
      cgpa: raw.student.cgpa,
      sgpa: raw.student.sgpa,
      percentage: raw.student.percentage,
      backlogs: raw.student.backlogs,
      academicStanding: raw.student.academic_standing,
      overallAttendance: raw.student.overall_attendance,
      topSubjects: (raw.student.top_subjects ?? []).map((s) => s.name ?? s.percentage?.toString() ?? "Subject").slice(0, 3),
      weakSubjects: (raw.student.weak_subjects ?? []).map((s) => s.name ?? "Subject").slice(0, 3),
      predictionsAvailable: raw.student.prediction_summary?.available ?? false,
      careerDomain: raw.student.career_readiness?.domain ?? null,
      nextClasses: (raw.student.upcoming_classes ?? []).map((c) => c.subject ?? "").filter(Boolean).slice(0, 3),
      notificationCount: (raw.student.recent_notifications ?? []).length,
    }
  }

  if (raw.faculty) {
    base.faculty = {
      name: raw.faculty.name,
      department: raw.faculty.department,
      designation: raw.faculty.designation,
      subjectsTaught: (raw.faculty.subjects_taught ?? []).map((s) => s.name ?? s.code ?? "").filter(Boolean).slice(0, 5),
      menteeCount: raw.faculty.total_mentees,
      flaggedCount: (raw.faculty.flagged_students ?? []).length,
      totalStudents: raw.faculty.class_summary?.total_students ?? null,
      avgCgpa: raw.faculty.class_summary?.avg_cgpa ?? null,
      avgAttendance: raw.faculty.class_summary?.avg_attendance ?? null,
    }
  }

  if (raw.admin) {
    base.admin = {
      totalStudents: raw.admin.total_students,
      totalFaculty: raw.admin.total_faculty,
      totalDepartments: raw.admin.total_departments,
      overallCgpa: raw.admin.overall_cgpa,
      overallAttendance: raw.admin.overall_attendance,
      flaggedCount: raw.admin.flagged_count ?? 0,
      departmentNames: (raw.admin.department_performance ?? []).map((d) => d.name ?? "").filter(Boolean).slice(0, 4),
    }
  }

  return base
}

export function Chatbot({
  role = "Student",
  targetStudentId = null,
  pageContext = null,
  className,
}: ChatbotProps) {
  const [isOpen, setIsOpen] = React.useState(false)
  const [isMinimized, setIsMinimized] = React.useState(false)
  const [isExpanded, setIsExpanded] = React.useState(false)
  const [messages, setMessages] = React.useState<UIMessage[]>([])
  const [input, setInput] = React.useState("")
  const [isLoading, setIsLoading] = React.useState(false)
  const [portal, setPortal] = React.useState<PortalSnapshot>({ role, available: false })
  const [contextLoaded, setContextLoaded] = React.useState(false)
  const isSendingRef = React.useRef(false)

  // Fetch role-specific portal context (ETL snapshot) once when opened. This
  // goes through the server-side Next.js route so session cookies never reach
  // the client bundle.
  const ensureContext = React.useCallback(async () => {
    if (contextLoaded) return
    setContextLoaded(true)
    try {
      const res = await fetch("/api/chat/context", {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(20000),
      })
      if (!res.ok) {
        setPortal({ role, available: false })
        return
      }
      const data: PortalContextResponse = await res.json()
      setPortal(mapPortalContext(data))
    } catch {
      setPortal({ role, available: false })
    }
  }, [contextLoaded, role])

  const handleToggle = () => {
    setIsOpen((prev) => {
      const next = !prev
      setIsMinimized(false)
      if (next) ensureContext()
      return next
    })
  }

  const handleClose = () => {
    setIsOpen(false)
    setIsMinimized(false)
    setIsExpanded(false)
  }

  const handleMinimize = () => {
    setIsMinimized((prev) => !prev)
  }

  const handleExpandToggle = () => {
    setIsExpanded((prev) => !prev)
  }

  const handleClear = () => {
    setMessages([])
  }

  const sendMessage = async (rawMessage: string) => {
    const text = rawMessage.trim()
    if (!text || isLoading || isSendingRef.current) return

    if (!contextLoaded) ensureContext()

    isSendingRef.current = true
    setIsLoading(true)

    const userMessage: UIMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput("")

    // Build bounded conversation history payload
    const recentHistory = [...messages, userMessage].slice(-10).map((m) => ({
      role: m.role,
      content: m.content,
    }))

    const reqPayload: ChatApiRequest = {
      message: text,
      target_student_id: role === "Faculty" || role === "Admin" ? targetStudentId : null,
      page_context: pageContext ?? null,
      conversation_history: recentHistory,
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 35000)

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reqPayload),
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!res.ok) {
        let errText = "Failed to communicate with AI chat service"
        try {
          const errData = await res.json()
          errText = errData.error || errData.message || errText
        } catch {
          // ignore
        }

        const errorMessage: UIMessage = {
          id: `error-${Date.now()}`,
          role: "assistant",
          content: res.status === 429 
            ? "The AI assistant is temporarily rate-limited. Please try again shortly." 
            : res.status === 504 || res.status === 503
            ? "The chat assistant is taking longer than usual to respond. Please try again in a moment."
            : errText,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          isError: true,
        }
        setMessages((prev) => [...prev, errorMessage])
        return
      }

      const data = await res.json()
      const assistantMessage: UIMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.message,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        status: data.status,
        intent: data.intent,
        toolName: data.tool_name,
        verifiedSources: data.verified_sources,
        provider: data.provider,
        model: data.model,
        isError: data.status === "rate_limited" && (!data.verified_sources || data.verified_sources.length === 0),
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (err: unknown) {
      clearTimeout(timeoutId)
      const isAbort = err instanceof Error && err.name === "AbortError"
      const content = isAbort
        ? "The chat assistant took longer than usual to respond. Please try asking your question again."
        : err instanceof Error
        ? `Connection error: ${err.message}`
        : "Network connection error. Please try again."

      const errorMessage: UIMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        isError: true,
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      isSendingRef.current = false
      setIsLoading(false)
    }
  }

  return (
    <>
      <ChatbotLauncher isOpen={isOpen} onClick={handleToggle} className={className} />

      <ChatbotPanel isOpen={isOpen} isMinimized={isMinimized} isExpanded={isExpanded} onClose={handleClose}>
        <ChatHeader
          role={role}
          portal={portal}
          onClose={handleClose}
          onMinimize={handleMinimize}
          onClear={handleClear}
          onExpandToggle={handleExpandToggle}
          isExpanded={isExpanded}
          messageCount={messages.length}
        />

        {!isMinimized && (
          <>
            <ChatMessageList
              messages={messages}
              isLoading={isLoading}
              role={role}
              portal={portal}
              onSelectSuggestion={(prompt) => sendMessage(prompt)}
              onRetry={(lastPrompt) => sendMessage(lastPrompt)}
            />

            <ChatInput
              input={input}
              setInput={setInput}
              onSend={() => sendMessage(input)}
              isLoading={isLoading}
            />
          </>
        )}
      </ChatbotPanel>
    </>
  )
}