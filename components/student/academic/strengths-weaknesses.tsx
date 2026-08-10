import {
  ArrowDownRight,
  CheckCircle2,
  CircleAlert,
  CircleX,
  Clock,
} from "lucide-react"

import type { NeedsAttentionItem, StrengthItem } from "@/lib/student-api"

import { Badge } from "@/components/ui/badge"
import { GradeBadge } from "@/components/shared/data/grade-badge"
import { EmptyState } from "@/components/shared/state/empty-state"

const CATEGORY_TONE = {
  Strong: "success" as const,
  Good: "secondary" as const,
}

const REASON_META: Record<
  string,
  { tone: "destructive" | "warning" | "muted"; icon: typeof CircleAlert }
> = {
  failed: { tone: "destructive", icon: CircleX },
  critical: { tone: "destructive", icon: CircleAlert },
  needs_attention: { tone: "warning", icon: CircleAlert },
  declining: { tone: "warning", icon: ArrowDownRight },
  incomplete: { tone: "muted", icon: Clock },
}

export function StrengthsWeaknesses({
  strengths,
  needsAttention,
}: {
  strengths: StrengthItem[]
  needsAttention: NeedsAttentionItem[]
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <h2 className="text-sm font-semibold">Strengths</h2>
        <p className="mt-1 mb-4 text-xs text-muted-foreground">
          Completed subjects with the strongest results. Product rule — not a prediction.
        </p>
        {strengths.length === 0 ? (
          <EmptyState
            icon={CheckCircle2}
            title="No strengths yet"
            description="Subject strengths will appear once final marks are published."
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {strengths.map((subject) => (
              <li
                key={subject.subject_code}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted/40 px-3 py-2.5"
              >
                <div className="flex min-w-0 flex-col gap-0.5">
                  <p className="truncate text-sm font-medium">{subject.subject_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {subject.subject_code} · Sem {subject.semester}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold tabular-nums">
                    {subject.percentage.toFixed(2)}%
                  </span>
                  <GradeBadge grade={subject.grade} />
                  <Badge variant={CATEGORY_TONE[subject.category as keyof typeof CATEGORY_TONE]}>
                    {subject.category}
                  </Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <h2 className="text-sm font-semibold">Needs attention</h2>
        <p className="mt-1 mb-4 text-xs text-muted-foreground">
          Prioritized by failure, low marks, declining trend and pending results.
        </p>
        {needsAttention.length === 0 ? (
          <EmptyState
            icon={CheckCircle2}
            title="Nothing needs attention"
            description="No subjects currently require attention based on the available data."
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {needsAttention.map((subject) => {
              const meta = REASON_META[subject.reason_code] ?? REASON_META.needs_attention
              const Icon = meta.icon
              return (
                <li
                  key={`${subject.subject_code}-${subject.reason_code}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted/40 px-3 py-2.5"
                >
                  <div className="flex min-w-0 items-center gap-2.5">
                    <Icon className="size-4 shrink-0 text-muted-foreground" />
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <p className="truncate text-sm font-medium">{subject.subject_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {subject.subject_code} · Sem {subject.semester}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {subject.percentage !== null && (
                      <span className="text-sm font-semibold tabular-nums">
                        {subject.percentage.toFixed(2)}%
                      </span>
                    )}
                    <GradeBadge grade={subject.grade} />
                    <Badge variant={meta.tone}>{subject.reason}</Badge>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
