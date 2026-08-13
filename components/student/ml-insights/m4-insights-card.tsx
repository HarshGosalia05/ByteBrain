import { AlertTriangle, CheckCircle2, Target } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type {
  MlExplanationResult,
  MlM4Explanation,
  MlModelInsight,
  MlPredictionResult,
} from "@/lib/student-api"

import { InputDetails } from "./input-details"
import { InsightUnavailable } from "./insight-unavailable"
import { ModelCard } from "./model-card"

type M4Prediction = Extract<MlPredictionResult, { model_id: "m4" }>

function levelTone(level: string): "success" | "warning" | "destructive" {
  if (level.toLowerCase() === "high") return "success"
  if (level.toLowerCase() === "medium") return "warning"
  return "destructive"
}

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
      <p className="text-xs font-semibold tracking-widest text-muted-foreground uppercase">
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
  explanation: MlExplanationResult
}) {
  const item = (explanation.explanations as MlM4Explanation[])[0]
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
          <Badge variant={levelTone(item.readiness_level)}>{item.readiness_level}</Badge>
          <Badge variant="muted">Rule-based score</Badge>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">{item.interpretation}</p>

      <div className="grid gap-4 sm:grid-cols-2">
        <FactorList title="Positive factors" items={item.positive_factors} positive />
        <FactorList title="Things to work on" items={item.risk_factors} positive={false} />
      </div>

      <p className="text-xs text-muted-foreground">
        This is a deterministic rule-based score, not a trained ML model prediction.
      </p>
      <InputDetails inputs={item.inputs} />
    </div>
  )
}

export function M4InsightsCard({ model }: { model: MlModelInsight }) {
  return (
    <ModelCard
      id="ml-insights-m4"
      icon={Target}
      title="Career readiness"
      subtitle="A rule-based readiness score with your current strengths and areas to work on."
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
