import { TrendingUp } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { FactorList } from "@/components/student/ml-insights/factor-list"
import { InputDetails } from "@/components/student/ml-insights/input-details"
import { ModelCard } from "@/components/student/ml-insights/model-card"
import type {
  FacultyMlExplanationResult,
  FacultyMlM2Explanation,
  FacultyMlModelInsight,
  FacultyMlPredictionResult,
} from "@/lib/faculty-api"

import { InsightUnavailable } from "./insight-unavailable"

type M2Prediction = Extract<FacultyMlPredictionResult, { model_id: "m2" }>

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
  explanation: FacultyMlExplanationResult
}) {
  const item = (explanation.explanations as FacultyMlM2Explanation[])[0]
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

      <div className="flex flex-col gap-2">
        <p className="text-[0.6875rem] font-semibold tracking-widest text-muted-foreground uppercase">
          Why
        </p>
        <FactorList factors={item.factors} />
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-[0.6875rem] font-semibold tracking-widest text-muted-foreground uppercase">
          What it means
        </p>
        <p className="text-sm text-muted-foreground">{item.interpretation}</p>
      </div>

      <InputDetails inputs={item.inputs} />
    </div>
  )
}

export function M2InsightsCard({ model }: { model: FacultyMlModelInsight }) {
  return (
    <ModelCard
      id="faculty-ml-insights-m2"
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
