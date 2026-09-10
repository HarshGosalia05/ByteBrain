"use client"

import * as React from "react"
import { Bot } from "lucide-react"
import { ChatMessageItem } from "./chat-message"
import { ChatSuggestions } from "./chat-suggestions"
import { useTranslation } from "@/lib/i18n"
import type { PortalSnapshot, UIMessage, UserRole } from "./types"

function welcomeText(role: UserRole, portal: PortalSnapshot): string {
  if (role === "Student") {
    const s = portal.student
    if (!s?.name) {
      return "Ask me about your academic performance, attendance, subjects, predictions, or career readiness."
    }
    const parts = [`Hi ${s.name}, you've got full access to your academic portal.`]
    const chips: string[] = []
    if (s.cgpa != null) chips.push(`CGPA ${s.cgpa}`)
    if (s.overallAttendance != null) chips.push(`attendance ${s.overallAttendance}%`)
    if (s.academicStanding) chips.push(`standing: ${s.academicStanding}`)
    if (chips.length) parts.push(`Right now: ${chips.join(" · ")}.`)
    if (s.weakSubjects && s.weakSubjects.length) {
      parts.push(`I can help you with ${s.weakSubjects.slice(0, 2).join(" and ")}.`)
    }
    parts.push("Ask me anything about your data below.")
    return parts.join(" ")
  }

  if (role === "Faculty") {
    const f = portal.faculty
    if (!f?.name) {
      return "Ask me about your students, subjects, flagged at-risk students, or department analytics."
    }
    const parts = [`Hi ${f.name}, your faculty portal is loaded.`]
    const chips: string[] = []
    if (f.subjectsTaught && f.subjectsTaught.length) {
      chips.push(`teaching ${f.subjectsTaught.length} subject(s)`)
    }
    if (f.menteeCount != null) chips.push(`${f.menteeCount} mentees`)
    if (f.totalStudents != null) chips.push(`${f.totalStudents} students in scope`)
    if (chips.length) parts.push(`You're currently ${chips.join(", ")}.`)
    if (f.flaggedCount != null && f.flaggedCount > 0) {
      parts.push(`Note: ${f.flaggedCount} student(s) in your scope need attention.`)
    }
    parts.push("How can I help you with your students today?")
    return parts.join(" ")
  }

  // Admin
  const a = portal.admin
  if (!a || a.totalStudents == null) {
    return "Ask me about institution-wide analytics, departments, academic trends, attendance, or ML insights."
  }
  const parts = ["Your institutional portal is loaded."]
  const chips: string[] = []
  if (a.totalStudents != null) chips.push(`${a.totalStudents} students`)
  if (a.totalFaculty != null) chips.push(`${a.totalFaculty} faculty`)
  if (a.totalDepartments != null) chips.push(`${a.totalDepartments} departments`)
  if (chips.length) parts.push(`Institution snapshot: ${chips.join(", ")}.`)
  if (a.flaggedCount != null && a.flaggedCount > 0) {
    parts.push(`${a.flaggedCount} flagged/at-risk students institution-wide.`)
  }
  parts.push("What would you like to drill into?")
  return parts.join(" ")
}

export function ChatMessageList({
  messages,
  isLoading,
  role = "Student",
  portal,
  onSelectSuggestion,
  onRetry,
}: {
  messages: UIMessage[]
  isLoading: boolean
  role?: UserRole
  portal?: PortalSnapshot
  onSelectSuggestion: (prompt: string) => void
  onRetry?: (lastUserMessage: string) => void
}) {
  const { t } = useTranslation()
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const bottomRef = React.useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages or loading state change
  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isLoading])

  const hasMessages = messages.length > 0

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto p-4 space-y-4 text-sm"
      tabIndex={0}
      aria-label="Conversation message history"
    >
      {!hasMessages && (
        <div className="flex flex-col items-center justify-center py-6 px-2 text-center space-y-4">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary border border-primary/20 shadow-xs">
            <Bot className="size-6" />
          </div>
          <div className="space-y-1 max-w-xs">
            <h4 className="text-sm font-semibold text-foreground">{t("CampusX Assistant")}</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {t(welcomeText(role, portal ?? { role, available: false }))}
            </p>
          </div>
          <div className="w-full pt-2">
            <ChatSuggestions role={role} portal={portal} onSelect={onSelectSuggestion} disabled={isLoading} />
          </div>
        </div>
      )}

      {hasMessages && (
        <div className="space-y-3.5">
          {messages.map((msg, index) => {
            // Find last user message before this error message for retry
            let lastUserContent = ""
            if (msg.isError) {
              for (let i = index - 1; i >= 0; i--) {
                if (messages[i].role === "user") {
                  lastUserContent = messages[i].content
                  break
                }
              }
            }

            return (
              <ChatMessageItem
                key={msg.id}
                message={msg}
                onRetry={msg.isError && lastUserContent ? () => onRetry?.(lastUserContent) : undefined}
              />
            )
          })}
        </div>
      )}

      {isLoading && (
        <div className="flex justify-start gap-2.5">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary border border-primary/20 mt-0.5">
            <Bot className="size-3.5" />
          </div>
          <div className="rounded-2xl rounded-tl-xs border border-border/80 bg-muted/40 px-3.5 py-2.5 text-xs shadow-xs text-muted-foreground flex items-center gap-2">
            <div className="flex items-center gap-1">
              <span className="size-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.3s]" />
              <span className="size-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.15s]" />
              <span className="size-1.5 rounded-full bg-primary animate-bounce" />
            </div>
            <span className="text-xs font-medium">{t("Thinking...")}</span>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}