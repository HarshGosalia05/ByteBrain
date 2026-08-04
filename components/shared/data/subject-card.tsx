"use client"

import Link from "next/link"
import {
  BookOpen,
  GraduationCap,
  TrendingUp,
  UserCheck,
  type LucideIcon,
} from "lucide-react"

import type { FacultyClassCard } from "@/lib/faculty-api"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

function formatPercent(value: number | null, digits = 1): string {
  return value !== null ? `${value.toFixed(digits)}%` : "—"
}

function Stat({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string
  icon: LucideIcon
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <div className="flex items-center gap-1 text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
        <Icon className="size-3 shrink-0" />
        <span className="truncate">{label}</span>
      </div>
      <p className="truncate text-sm font-semibold tabular-nums">{value}</p>
    </div>
  )
}

export function SubjectCard({
  card,
  href,
  onClick,
}: {
  card: FacultyClassCard
  href?: string
  onClick?: () => void
}) {
  const content = (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-xs text-muted-foreground">{card.subject_code}</p>
          <h3 className="mt-1 truncate text-sm font-semibold" title={card.subject_name}>
            {card.subject_name}
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Sem {card.semester_no} · {card.academic_year}
          </p>
        </div>
        <Badge variant="secondary">{card.credits ?? "—"} credits</Badge>
      </div>
      <div className="mt-auto grid grid-cols-2 gap-3 border-t border-border pt-3 sm:grid-cols-4">
        <Stat label="Students" value={card.class_strength.toString()} icon={GraduationCap} />
        <Stat label="Attendance" value={formatPercent(card.average_attendance)} icon={UserCheck} />
        <Stat label="Performance" value={formatPercent(card.average_percentage)} icon={TrendingUp} />
        <Stat label="Pass rate" value={formatPercent(card.pass_percentage, 0)} icon={BookOpen} />
      </div>
    </>
  )

  const baseClasses =
    "flex h-full flex-col gap-4 rounded-xl bg-card p-4 ring-1 ring-foreground/10 transition-colors hover:bg-muted/40"

  if (href) {
    return (
      <Link
        href={href}
        className={cn(
          baseClasses,
          "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        )}
      >
        {content}
      </Link>
    )
  }

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cn(baseClasses, "w-full cursor-pointer text-left")}
      >
        {content}
      </button>
    )
  }

  return <div className={baseClasses}>{content}</div>
}
