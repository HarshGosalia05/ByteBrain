import * as React from "react"
import { Bot } from "lucide-react"
import { cn } from "@/lib/utils"

export function ChatbotLauncher({
  isOpen,
  onClick,
  unreadCount = 0,
  className,
}: {
  isOpen: boolean
  onClick: () => void
  unreadCount?: number
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={isOpen ? "Close AI Chatbot" : "Open AI Chatbot"}
      aria-expanded={isOpen}
      className={cn(
        "fixed bottom-5 right-5 z-40 flex size-13 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-all duration-200 hover:scale-105 hover:shadow-xl active:scale-95 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 cursor-pointer",
        isOpen && "rotate-90 bg-muted text-muted-foreground hover:bg-muted/80",
        className
      )}
    >
      <Bot className="size-6 transition-transform" />

      {unreadCount > 0 && !isOpen && (
        <span className="absolute -top-1 -right-1 flex size-5 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-destructive-foreground ring-2 ring-background">
          {unreadCount}
        </span>
      )}
    </button>
  )
}
