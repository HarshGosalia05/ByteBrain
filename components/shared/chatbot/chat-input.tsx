"use client"

import * as React from "react"
import { Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useTranslation } from "@/lib/i18n"

export function ChatInput({
  input,
  setInput,
  onSend,
  isLoading,
  maxLength = 500,
}: {
  input: string
  setInput: (val: string) => void
  onSend: () => void
  isLoading: boolean
  maxLength?: number
}) {
  const { t } = useTranslation()
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  // Auto resize textarea height
  React.useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }, [input])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      if (!isLoading && input.trim()) {
        onSend()
      }
    }
  }

  const canSend = Boolean(input.trim()) && !isLoading

  return (
    <div className="border-t border-border/80 bg-background/80 p-3 select-none">
      <div className="relative flex items-end gap-2 rounded-xl border border-input bg-muted/30 p-1.5 focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-primary/20 transition-all">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value.slice(0, maxLength))}
          onKeyDown={handleKeyDown}
          placeholder={t("Ask a question...")}
          rows={1}
          disabled={isLoading}
          aria-label={t("Ask a question...")}
          className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground focus:outline-hidden disabled:opacity-50 disabled:cursor-not-allowed leading-relaxed"
        />

        <Button
          type="button"
          size="icon-xs"
          onClick={onSend}
          disabled={!canSend}
          aria-label={t("Send message")}
          className="size-7 shrink-0 rounded-lg cursor-pointer transition-transform active:scale-95 disabled:cursor-not-allowed"
        >
          <Send className="size-3.5" />
        </Button>
      </div>

      <div className="mt-1.5 flex items-center justify-between px-1 text-[10px] text-muted-foreground select-none">
        <span>Enter to send, Shift+Enter for newline</span>
        <span>
          {input.length}/{maxLength}
        </span>
      </div>
    </div>
  )
}
