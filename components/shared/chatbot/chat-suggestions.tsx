"use client"

import * as React from "react"
import { Sparkles } from "lucide-react"
import { useTranslation } from "@/lib/i18n"
import type { PortalSnapshot, UserRole } from "./types"

function studentSuggestions(portal: PortalSnapshot): string[] {
  const s = portal.student
  const suggestions: string[] = []

  if (s?.sgpa != null || s?.cgpa != null || s?.percentage != null) {
    suggestions.push("How is my academic performance?")
  }
  if (s?.topSubjects && s.topSubjects.length > 0) {
    suggestions.push(`What are my strongest subjects?`)
  }
  if (s?.weakSubjects && s.weakSubjects.length > 0) {
    suggestions.push(`Which subjects do I need to improve?`)
  }
  if (s?.overallAttendance != null) {
    suggestions.push("Show my attendance overview")
  }
  if (s?.predictionsAvailable) {
    suggestions.push("Explain my ML predictions")
  }
  // if (s?.careerDomain) {
  //   suggestions.push(`How ready am I for a career in ${s.careerDomain}?`)
  // } else {
  //   suggestions.push("What career is suitable for me?")
  // }

  // Fallbacks ensure the empty state always has useful starting points.
  if (suggestions.length < 3) {
    const fallbacks = [
      "How is my academic performance?",
      "What is my next class today?",
      "Explain my ML predictions",
    ]
    for (const fb of fallbacks) {
      if (!suggestions.includes(fb)) suggestions.push(fb)
    }
  }
  return suggestions.slice(0, 5)
}

function facultySuggestions(portal: PortalSnapshot): string[] {
  const f = portal.faculty
  const suggestions: string[] = []

  if (f?.avgCgpa != null || f?.totalStudents != null) {
    suggestions.push("Show my class performance summary")
  }
  if (f?.subjectsTaught && f.subjectsTaught.length > 0) {
    suggestions.push(`What subjects do I teach?`)
  }
  if (f?.flaggedCount != null && f.flaggedCount > 0) {
    suggestions.push(`Show the ${f.flaggedCount} flagged students in my scope`)
  }
  if (f?.menteeCount != null) {
    suggestions.push(`Show my ${f.menteeCount} mentees`)
  }
  if (f?.avgAttendance != null) {
    suggestions.push("Check attendance analytics for my students")
  }

  if (suggestions.length < 3) {
    const fallbacks = [
      "Show student performance summary",
      "Show flagged at-risk students",
      "Review ML prediction insights",
    ]
    for (const fb of fallbacks) {
      if (!suggestions.includes(fb)) suggestions.push(fb)
    }
  }
  return suggestions.slice(0, 5)
}

function adminSuggestions(portal: PortalSnapshot): string[] {
  const a = portal.admin
  const suggestions: string[] = []

  if (a?.totalStudents != null || a?.overallCgpa != null) {
    suggestions.push("Show college-wide executive summary")
  }
  if (a?.departmentNames && a.departmentNames.length > 1) {
    suggestions.push("Compare department performance")
  }
  if (a?.flaggedCount != null) {
    suggestions.push(`Show institution-wide at-risk students`)
  }
  if (a?.overallAttendance != null) {
    suggestions.push("View institutional attendance trends")
  }

  if (suggestions.length < 3) {
    const fallbacks = [
      "Show college-wide executive summary",
      "Compare department performance",
      "Review ML intelligence metrics",
    ]
    for (const fb of fallbacks) {
      if (!suggestions.includes(fb)) suggestions.push(fb)
    }
  }
  return suggestions.slice(0, 5)
}

export function roleSuggestions(role: UserRole, portal: PortalSnapshot): string[] {
  if (role === "Student") return studentSuggestions(portal)
  if (role === "Faculty") return facultySuggestions(portal)
  return adminSuggestions(portal)
}

export function ChatSuggestions({
  role,
  portal,
  onSelect,
  disabled,
}: {
  role: UserRole
  portal?: PortalSnapshot
  onSelect: (prompt: string) => void
  disabled?: boolean
}) {
  const { t } = useTranslation()
  const suggestions = roleSuggestions(role, portal ?? { role, available: false })

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