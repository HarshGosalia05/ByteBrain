import * as React from "react"
import { AlertCircle, Bot, CheckCircle2, RotateCw, User } from "lucide-react"
import { cn } from "@/lib/utils"
import { ChatMarkdown } from "./chat-markdown"
import { Button } from "@/components/ui/button"
import type { UIMessage } from "./types"

export function ChatMessageItem({
  message,
  onRetry,
}: {
  message: UIMessage
  onRetry?: () => void
}) {
  const isUser = message.role === "user"
  const isError = Boolean(message.isError)

  return (
    <div
      className={cn(
        "flex gap-2.5 items-start text-xs leading-relaxed",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <div
          className={cn(
            "flex size-7 shrink-0 items-center justify-center rounded-full border mt-0.5 shadow-2xs",
            isError
              ? "bg-destructive/10 text-destructive border-destructive/20"
              : "bg-primary/10 text-primary border-primary/20"
          )}
        >
          {isError ? <AlertCircle className="size-3.5" /> : <Bot className="size-3.5" />}
        </div>
      )}

      <div
        className={cn(
          "max-w-[84%] rounded-2xl px-3.5 py-2.5 shadow-xs transition-colors",
          isUser
            ? "bg-primary text-primary-foreground rounded-tr-xs"
            : isError
            ? "bg-destructive/10 text-destructive border border-destructive/20 rounded-tl-xs"
            : "bg-muted/60 text-foreground border border-border/70 rounded-tl-xs"
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : isError ? (
          <div className="space-y-2">
            <p className="font-medium text-destructive">{message.content}</p>
            {onRetry && (
              <Button
                type="button"
                variant="outline"
                size="xs"
                onClick={onRetry}
                className="gap-1.5 border-destructive/30 text-destructive hover:bg-destructive/10 cursor-pointer h-7 text-[11px]"
              >
                <RotateCw className="size-3" />
                <span>Retry</span>
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <ChatMarkdown content={message.content} />

            {/* Verified Data Sources Footer */}
            {message.verifiedSources && message.verifiedSources.length > 0 && (
              <div className="pt-1.5 mt-1.5 border-t border-border/50 flex items-center flex-wrap gap-1 text-[10px] text-muted-foreground">
                <CheckCircle2 className="size-2.5 text-emerald-500" />
                <span>Verified Source:</span>
                {message.verifiedSources.map((source) => (
                  <span
                    key={source}
                    className="font-mono bg-background/80 px-1.5 py-0.2 rounded border border-border/60 text-[9px] text-foreground"
                  >
                    {source}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        <div
          className={cn(
            "mt-1 text-[10px] select-none text-right opacity-70",
            isUser ? "text-primary-foreground/80" : "text-muted-foreground"
          )}
        >
          {message.timestamp}
        </div>
      </div>

      {isUser && (
        <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground border border-border/80 mt-0.5 shadow-2xs">
          <User className="size-3.5" />
        </div>
      )}
    </div>
  )
}
