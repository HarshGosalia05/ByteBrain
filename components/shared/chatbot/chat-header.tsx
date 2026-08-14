import * as React from "react"
import { Bot, Minimize2, Trash2, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { UserRole } from "./types"

const ROLE_SUBTITLES: Record<UserRole, string> = {
  Student: "Academic & Career Assistant",
  Faculty: "Faculty Analytics Assistant",
  Admin: "Institutional Intelligence Assistant",
}

export function ChatHeader({
  role = "Student",
  onClose,
  onMinimize,
  onClear,
  messageCount,
}: {
  role?: UserRole
  onClose: () => void
  onMinimize?: () => void
  onClear: () => void
  messageCount: number
}) {
  return (
    <div className="flex items-center justify-between border-b border-border/80 bg-muted/40 px-4 py-3 select-none">
      <div className="flex items-center gap-2.5">
        <div className="relative flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20 shadow-xs">
          <Bot className="size-4.5" />
          <span className="absolute -bottom-0.5 -right-0.5 size-2 rounded-full bg-emerald-500 ring-2 ring-background" />
        </div>
        <div>
          <div className="flex items-center gap-1.5">
            <h3 className="text-xs font-semibold tracking-tight text-foreground">KenexAI Assistant</h3>
            <span className="rounded-sm bg-primary/10 px-1 py-0.2 text-[9px] font-medium text-primary">
              Grounded AI
            </span>
          </div>
          <p className="text-[11px] text-muted-foreground">
            {ROLE_SUBTITLES[role] || "Grounded Guidance"}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1">
        {messageCount > 0 && (
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            onClick={onClear}
            title="Clear conversation"
            aria-label="Clear conversation history"
            className="text-muted-foreground hover:text-destructive"
          >
            <Trash2 className="size-3.5" />
          </Button>
        )}
        {onMinimize && (
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            onClick={onMinimize}
            title="Minimize"
            aria-label="Minimize chatbot window"
            className="text-muted-foreground hover:text-foreground"
          >
            <Minimize2 className="size-3.5" />
          </Button>
        )}
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          onClick={onClose}
          title="Close"
          aria-label="Close chatbot window"
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="size-4" />
        </Button>
      </div>
    </div>
  )
}
