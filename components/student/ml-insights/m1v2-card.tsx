import { BookOpen, CircleAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  m1V2GradeTone,
  type M1V2PredictionData,
  type M1V2SubjectPrediction,
} from "@/lib/m1v2-prediction"

import { ModelCard } from "./model-card"

function SubjectTile({ item }: { item: M1V2SubjectPrediction }) {
  const displayName = item.subject_name || item.subject_id
  const currentInternal =
    item.input_features.internal_marks !== null &&
    item.input_features.internal_marks !== undefined
      ? item.input_features.internal_marks
      : null
  const diff =
    currentInternal !== null ? item.predicted_end_sem_marks - currentInternal : null

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-foreground/10 bg-background/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{displayName}</p>
          <p className="text-[0.6875rem] text-muted-foreground">
            Semester {item.semester_no}
          </p>
        </div>
        <Badge variant={m1V2GradeTone(item.grade_band)}>{item.grade_band}</Badge>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
            Predicted
          </p>
          <p className="text-2xl font-bold tabular-nums">
            {item.predicted_end_sem_marks.toFixed(1)}
            <span className="text-sm font-normal text-muted-foreground"> / {item.target_max}</span>
          </p>
          {item.grade_label && (
            <p className="text-xs text-muted-foreground">{item.grade_label}</p>
          )}
        </div>
        <div>
          <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
            Current
          </p>
          <p className="text-2xl font-semibold tabular-nums">
            {currentInternal !== null ? currentInternal.toFixed(1) : "—"}
            {currentInternal !== null && (
              <span className="text-sm font-normal text-muted-foreground"> / {item.target_max}</span>
            )}
          </p>
          {diff !== null && (
            <p
              className={`text-xs font-medium tabular-nums ${diff >= 0 ? "text-success" : "text-destructive"}`}
            >
              {diff >= 0 ? "▲" : "▼"} {Math.abs(diff).toFixed(1)}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export function M1V2Card({ data }: { data: M1V2PredictionData }) {
  return (
    <ModelCard
      id="ml-insights-m1v2"
      icon={BookOpen}
      title="Subject end-semester predictions (M1 V2)"
      subtitle="Predicted end-sem marks on the 0–70 scale against your current marks, with the projected grade band for each subject."
      badge={<Badge variant="secondary">M1 V2 · Subjects</Badge>}
    >
      {data.subjects.length === 0 ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-5"
        >
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-medium">Not available yet</p>
            <p className="text-xs text-muted-foreground">
              We need more academic records before this prediction can be generated.
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
              "Predicted end-sem marks are model estimates, not actual results. Uncertainty is unavailable for this model."}{" "}
            Model version {data.model_version}.
          </p>
        </div>
      )}
    </ModelCard>
  )
}
