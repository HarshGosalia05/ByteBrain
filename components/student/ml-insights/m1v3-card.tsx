import { BookOpen, CircleAlert, TrendingUp } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  m1V3CurrentMidSem,
  m1V3GradeTone,
  m1V3PredictedEndSem,
  M1V3_ALGO,
  M1V3_FEATURE_COUNT,
  M1V3_MODEL_VERSION,
  type M1V3PredictionData,
  type M1V3SubjectPrediction,
} from "@/lib/m1v3-prediction"

import { ModelCard } from "./model-card"

// Progress bar for predicted marks on the /70 scale.
function ScoreBar({ value, max = 70 }: { value: number; max?: number }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const colour =
    pct >= 85
      ? "bg-emerald-500"
      : pct >= 70
        ? "bg-green-500"
        : pct >= 55
          ? "bg-blue-500"
          : pct >= 40
            ? "bg-yellow-500"
            : pct >= 30
              ? "bg-orange-400"
              : "bg-red-500"
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-foreground/10">
      <div
        className={`h-full rounded-full transition-all ${colour}`}
        style={{ width: `${pct}%` }}
        aria-hidden="true"
      />
    </div>
  )
}

// Compact stat chip shown in the features row.
function StatChip({
  label,
  value,
  suffix = "",
}: {
  label: string
  value: number | null | undefined
  suffix?: string
}) {
  if (value === null || value === undefined) return null
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-[0.6rem] font-medium tracking-widest text-muted-foreground uppercase">
        {label}
      </p>
      <p className="text-sm font-semibold tabular-nums">
        {value.toFixed(1)}
        {suffix && (
          <span className="text-xs font-normal text-muted-foreground">
            {suffix}
          </span>
        )}
      </p>
    </div>
  )
}

function SubjectTile({ item }: { item: M1V3SubjectPrediction }) {
  const displayName = item.subject_name || item.subject_id
  const predicted = m1V3PredictedEndSem(item)
  const current = m1V3CurrentMidSem(item)
  const f = item.input_features

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-foreground/10 bg-background/40 p-4">
      {/* Header — name + grade badge */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold leading-snug">{displayName}</p>
          <p className="text-[0.6875rem] text-muted-foreground">
            Semester {item.semester_no}
            {f.credits != null && (
              <span className="ml-1 text-muted-foreground/60">
                · {f.credits} cr
              </span>
            )}
          </p>
        </div>
        <Badge variant={m1V3GradeTone(item.grade_band)}>{item.grade_band}</Badge>
      </div>

      {/* Predicted + Current marks */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
            Predicted
          </p>
          <p className="text-2xl font-bold tabular-nums">
            {predicted.toFixed(1)}
            <span className="text-sm font-normal text-muted-foreground">
              {" "}
              / {item.target_max}
            </span>
          </p>
          {item.grade_label && (
            <p className="text-xs text-muted-foreground">{item.grade_label}</p>
          )}
        </div>
        <div>
          <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
            Mid-sem
          </p>
          <p className="text-2xl font-semibold tabular-nums">
            {current.value !== null ? current.value.toFixed(1) : "—"}
            {current.value !== null && (
              <span className="text-sm font-normal text-muted-foreground">
                {" "}
                / {current.max}
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Score progress bar */}
      <ScoreBar value={predicted} max={item.target_max} />

      {/* Additional input features from the 38-feature contract */}
      {(f.pre_endsem_assessment_pct != null ||
        f.assignment_score != null ||
        f.quiz_avg_marks != null ||
        f.submission_delay_days != null ||
        f.internal_marks != null) && (
        <div className="flex flex-wrap gap-x-4 gap-y-2 border-t border-foreground/10 pt-3">
          <StatChip label="Internal" value={f.internal_marks} suffix=" /20" />
          <StatChip
            label="Pre-endsem"
            value={f.pre_endsem_assessment_pct}
            suffix="%"
          />
          <StatChip
            label="Assignment"
            value={f.assignment_score}
            suffix="%"
          />
          <StatChip label="Quiz avg" value={f.quiz_avg_marks} suffix=" /100" />
          {f.submission_delay_days != null && f.submission_delay_days > 0 && (
            <StatChip
              label="Submit delay"
              value={f.submission_delay_days}
              suffix="d"
            />
          )}
        </div>
      )}
    </div>
  )
}

export function M1V3Card({ data }: { data: M1V3PredictionData }) {
  return (
    <ModelCard
      id="ml-insights-m1v3"
      icon={BookOpen}
      title="Subject end-semester predictions"
      subtitle={`Predicted end-sem marks (0–70 scale) with grade band per subject, powered by ${M1V3_ALGO} on ${M1V3_FEATURE_COUNT} features.`}
      badge={<Badge variant="secondary">M1 V3 · HGB · {M1V3_FEATURE_COUNT} Features</Badge>}
    >
      {data.subjects.length === 0 ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-5"
        >
          <CircleAlert
            className="mt-0.5 size-4 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-medium">Not available yet</p>
            <p className="text-xs text-muted-foreground">
              We need more academic records before this prediction can be
              generated.
            </p>
          </div>
        </div>
      ) : (
        <div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.subjects.map((item) => (
              <SubjectTile key={item.subject_id} item={item} />
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            {data.note ??
              `Predicted end-sem marks are model estimates, not actual results. Generated by ${M1V3_MODEL_VERSION} (${M1V3_ALGO}, ${M1V3_FEATURE_COUNT}-feature contract) trained on real CampusX data.`}{" "}
            Model version {data.model_version}.
          </p>
        </div>
      )}
    </ModelCard>
  )
}
