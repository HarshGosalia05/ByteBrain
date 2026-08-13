import { TrendingUp } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type {
  MlExplanationResult,
  MlM2Explanation,
  MlModelInsight,
  MlPredictionResult,
} from "@/lib/student-api"

import { FactorList } from "./factor-list"
import { InputDetails } from "./input-details"
import { InsightUnavailable } from "./insight-unavailable"
import { ModelCard } from "./model-card"

type M2Prediction = Extract<MlPredictionResult, { model_id: "m2" }>

function StatValue({
  label,
  value,
  hint,
  hintTone,
}: {
  label: string
  value: string
  hint?: string
  hintTone?: "success" | "warning"
}) {
  return (
    <div className="rounded-lg bg-muted/40 px-3 py-3">
      <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
        {label}
      </p>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      {hint && (
        <p className={`text-xs font-medium tabular-nums ${hintTone === "warning" ? "text-chart-3" : "text-chart-2"}`}>
          {hint}
        </p>
      )}
    </div>
  )
}

function M2Body({
  prediction,
  explanation,
}: {
  prediction: M2Prediction
  explanation: MlExplanationResult
}) {
  const item = (explanation.explanations as MlM2Explanation[])[0]
  if (!item) {
    return (
      <p className="text-sm text-muted-foreground">
        {prediction.prediction_count === 0
          ? "No next-semester prediction recorded yet."
          : "The next-semester prediction is not available yet."}
      </p>
    )
  }
  const delta = item.projected_delta_percentage
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatValue
          label="Predicted SGPA"
          value={item.predicted_next_semester_sgpa.toFixed(2)}
        />
        <StatValue
          label="Predicted percentage"
          value={`${item.predicted_next_semester_percentage.toFixed(1)}%`}
        />
        <StatValue
          label="Vs current semester"
          value={item.current_percentage === null ? "—" : `${item.current_percentage.toFixed(1)}%`}
          hint={
            delta === null
              ? undefined
              : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)} points`
          }
          hintTone={delta === null ? undefined : delta >= 0 ? "success" : "warning"}
        />
      </div>
      <p className="text-sm text-muted-foreground">{item.interpretation}</p>
      <div className="flex flex-col gap-3">
        <FactorList factors={item.factors} />
        <InputDetails inputs={item.inputs} />
      </div>
    </div>
  )
}

export function M2InsightsCard({ model }: { model: MlModelInsight }) {
  return (
    <ModelCard
      id="ml-insights-m2"
      icon={TrendingUp}
      title="Next-semester performance"
      subtitle="Predicted SGPA and percentage for the coming semester, compared with the current one."
      badge={<Badge variant="secondary">M2 · Next semester</Badge>}
    >
      {!model.available ? (
        <InsightUnavailable model={model} />
      ) : (
        <M2Body
          prediction={model.prediction as M2Prediction}
          explanation={model.explanation}
        />
      )}
    </ModelCard>
  )
}
