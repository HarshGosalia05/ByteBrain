"use client"

import * as React from "react"
import { Sparkles } from "lucide-react"
import { useTranslation } from "@/lib/i18n"
import type { UserRole } from "./types"

const ROLE_SUGGESTIONS: Record<UserRole, string[]> = {
  Student: [
    "How is my academic performance?",
    "Show my attendance overview",
    "Which subjects need attention?",
    "Explain my ML predictions",
    "What career is suitable for me?",
  ],
  Faculty: [
    "Show student performance summary",
    "Check subject-wise attendance analytics",
    "Show flagged at-risk students",
    "Review ML prediction insights",
    "View department academic overview",
  ],
  Admin: [
    "Show college-wide executive summary",
    "Compare department performance",
    "View institutional attendance trends",
    "Show flagged at-risk students",
    "Review ML intelligence metrics",
  ],
}

export function ChatSuggestions({
  role,
  onSelect,
  disabled,
}: {
  role: UserRole
  onSelect: (prompt: string) => void
  disabled?: boolean
}) {
  const { t } = useTranslation()
  const suggestions = ROLE_SUGGESTIONS[role] || ROLE_SUGGESTIONS.Student

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
        <Sparkles className="size-3 text-primary" />
        <span>{t("Suggested queries")}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {suggestions.map((prompt) => (
          <button
            key={prompt}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(prompt)}
            className="rounded-full border border-border/80 bg-background/80 px-2.5 py-1 text-left text-xs text-muted-foreground transition hover:border-primary/50 hover:bg-muted hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
          >
            {t(prompt)}
          </button>
        ))}
      </div>
    </div>
  )
}
