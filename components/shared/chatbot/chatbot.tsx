"use client"

import * as React from "react"
import { ChatbotLauncher } from "./chatbot-launcher"
import { ChatbotPanel } from "./chatbot-panel"
import { ChatHeader } from "./chat-header"
import { ChatMessageList } from "./chat-message-list"
import { ChatInput } from "./chat-input"
import type { ChatbotProps, UIMessage } from "./types"
import type { ChatApiRequest } from "@/lib/chat-api"

export function Chatbot({
  role = "Student",
  targetStudentId = null,
  className,
}: ChatbotProps) {
  const [isOpen, setIsOpen] = React.useState(false)
  const [isMinimized, setIsMinimized] = React.useState(false)
  const [messages, setMessages] = React.useState<UIMessage[]>([])
  const [input, setInput] = React.useState("")
  const [isLoading, setIsLoading] = React.useState(false)
  const isSendingRef = React.useRef(false)

  const handleToggle = () => {
    setIsOpen((prev) => !prev)
    setIsMinimized(false)
  }

  const handleClose = () => {
    setIsOpen(false)
    setIsMinimized(false)
  }

  const handleMinimize = () => {
    setIsMinimized((prev) => !prev)
  }

  const handleClear = () => {
    setMessages([])
  }

  const sendMessage = async (rawMessage: string) => {
    const text = rawMessage.trim()
    if (!text || isLoading || isSendingRef.current) return

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
      conversation_history: recentHistory,
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 20000)

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
      const msg = isAbort
        ? "Request timed out. The chat assistant took too long to respond. Please try again."
        : err instanceof Error
        ? err.message
        : "Network error"

      const errorMessage: UIMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: isAbort ? msg : `Connection error: ${msg}`,
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

      <ChatbotPanel isOpen={isOpen} isMinimized={isMinimized} onClose={handleClose}>
        <ChatHeader
          role={role}
          onClose={handleClose}
          onMinimize={handleMinimize}
          onClear={handleClear}
          messageCount={messages.length}
        />

        {!isMinimized && (
          <>
            <ChatMessageList
              messages={messages}
              isLoading={isLoading}
              role={role}
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
