"use client"

import * as React from "react"
import { Bot } from "lucide-react"
import { ChatMessageItem } from "./chat-message"
import { ChatSuggestions } from "./chat-suggestions"
import { useTranslation } from "@/lib/i18n"
import type { UIMessage, UserRole } from "./types"

export function ChatMessageList({
  messages,
  isLoading,
  role = "Student",
  onSelectSuggestion,
  onRetry,
}: {
  messages: UIMessage[]
  isLoading: boolean
  role?: UserRole
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
            <h4 className="text-sm font-semibold text-foreground">{t("KenexAI Assistant")}</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {t("Ask me about your academic performance, attendance, subjects, predictions, or career readiness.")}
            </p>
          </div>
          <div className="w-full pt-2">
            <ChatSuggestions role={role} onSelect={onSelectSuggestion} disabled={isLoading} />
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
