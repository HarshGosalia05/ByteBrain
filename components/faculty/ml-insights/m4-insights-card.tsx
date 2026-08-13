import { AlertTriangle, CheckCircle2, Target } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { InputDetails } from "@/components/student/ml-insights/input-details"
import { ModelCard } from "@/components/student/ml-insights/model-card"
import {
  facultyMlReadinessTone,
  type FacultyMlExplanationResult,
  type FacultyMlM4Explanation,
  type FacultyMlModelInsight,
  type FacultyMlPredictionResult,
} from "@/lib/faculty-api"

import { InsightUnavailable } from "./insight-unavailable"

type M4Prediction = Extract<FacultyMlPredictionResult, { model_id: "m4" }>

function FactorList({
  title,
  items,
  positive,
}: {
  title: string
  items: string[]
  positive: boolean
}) {
  const Icon = positive ? CheckCircle2 : AlertTriangle
  const toneClass = positive ? "text-chart-2" : "text-chart-3"
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <p className="text-[0.6875rem] font-semibold tracking-widest text-muted-foreground uppercase">
        {title}
      </p>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {positive ? "Nothing flagged yet." : "Nothing flagged."}
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {items.map((factor, index) => (
            <li key={index} className="flex items-start gap-2 text-sm">
              <Icon className={`mt-0.5 size-4 shrink-0 ${toneClass}`} aria-hidden="true" />
              <span>{factor}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function M4Body({
  prediction,
  explanation,
}: {
  prediction: M4Prediction
  explanation: FacultyMlExplanationResult
}) {
  const item = (explanation.explanations as FacultyMlM4Explanation[])[0]
  if (!item) {
    return (
      <p className="text-sm text-muted-foreground">
        {prediction.prediction_count === 0
          ? "No career readiness score recorded yet."
          : "The career readiness score is not available yet."}
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-end gap-1.5">
          <p className="text-4xl font-semibold tabular-nums">{item.readiness_score.toFixed(1)}</p>
          <span className="pb-1 text-sm text-muted-foreground">/ 100</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={facultyMlReadinessTone(item.readiness_level)}>{item.readiness_level}</Badge>
          <Badge variant="muted">Rule-based score</Badge>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-[0.6875rem] font-semibold tracking-widest text-muted-foreground uppercase">
          What it means
        </p>
        <p className="text-sm text-muted-foreground">{item.interpretation}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <FactorList title="Positive factors" items={item.positive_factors} positive />
        <FactorList title="Areas for support" items={item.risk_factors} positive={false} />
      </div>

      <p className="text-xs text-muted-foreground">
        This is a deterministic rule-based score, not a trained ML model prediction.
      </p>
      <InputDetails inputs={item.inputs} />
    </div>
  )
}

export function M4InsightsCard({ model }: { model: FacultyMlModelInsight }) {
  return (
    <ModelCard
      id="faculty-ml-insights-m4"
      icon={Target}
      title="Career readiness"
      subtitle="A rule-based readiness score with the student's current strengths and areas where support may help."
      badge={<Badge variant="muted">M4 · Rule-based</Badge>}
    >
      {!model.available ? (
        <InsightUnavailable model={model} />
      ) : (
        <M4Body
          prediction={model.prediction as M4Prediction}
          explanation={model.explanation}
        />
      )}
    </ModelCard>
  )
}
