import { Info, ScanSearch } from "lucide-react"

import type { LearningGapItem } from "@/lib/student-api"

import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/state/empty-state"

const SIGNAL_META: Record<string, { tone: "warning" | "secondary"; label: string }> = {
  assessment_progression_gap: { tone: "warning", label: "Assessment gap" },
  repeated_low_performance: { tone: "warning", label: "Repeated low performance" },
  repeated_weakness: { tone: "secondary", label: "Repeated weakness" },
}

export function LearningGaps({ gaps }: { gaps: LearningGapItem[] }) {
  if (gaps.length === 0) {
    return (
      <EmptyState
        icon={ScanSearch}
        title="No learning-gap signals detected"
        description="No learning-gap signals were detected from the available assessment data."
      />
    )
  }

  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <h2 className="text-sm font-semibold">Learning gaps</h2>
      <p className="mt-1 mb-4 flex items-start gap-1.5 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-3 shrink-0" />
        Deterministic signals from your own assessment data — not a diagnosis.
      </p>
      <ul className="flex flex-col gap-2">
        {gaps.map((gap, index) => {
          const meta =
            SIGNAL_META[gap.signal_code] ?? {
              tone: "secondary" as const,
              label: gap.signal,
            }
          return (
            <li
              key={`${gap.subject_code}-${gap.signal_code}-${index}`}
              className="flex flex-col gap-1 rounded-lg bg-muted/40 px-3 py-2.5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium">{gap.subject_name}</p>
                <Badge variant={meta.tone}>{meta.label}</Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {gap.subject_code} · Sem {gap.semester}
              </p>
              <p className="text-sm text-muted-foreground">{gap.detail}</p>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
