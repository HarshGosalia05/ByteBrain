import { AlertTriangle, ArrowRight, CheckCircle2, ShieldCheck } from "lucide-react"

import type {
  MlExplanationResult,
  MlExplanationFactor,
  MlM3Explanation,
  MlModelInsight,
  MlPredictionResult,
} from "@/lib/student-api"

import { InsightUnavailable } from "./insight-unavailable"
import { ModelCard } from "./model-card"
import { SectionLabel, SignalGrid } from "./signal-list"

type M3Prediction = Extract<MlPredictionResult, { model_id: "m3" }>

function ReasonList({ factors }: { factors: MlExplanationFactor[] }) {
  if (factors.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No specific signals were flagged for this result.
      </p>
    )
  }
  return (
    <ul className="flex flex-col gap-2">
      {factors.map((factor, index) => {
        const positive = factor.kind === "positive"
        const Icon = positive ? CheckCircle2 : AlertTriangle
        return (
          <li
            key={index}
            className="flex items-start gap-2 rounded-lg border border-foreground/10 bg-background/40 px-3 py-2 text-sm"
          >
            <Icon
              className={`mt-0.5 size-4 shrink-0 ${positive ? "text-chart-2" : "text-chart-3"}`}
              aria-hidden="true"
            />
            <span className="min-w-0">{factor.detail}</span>
          </li>
        )
      })}
    </ul>
  )
}

function M3Body({
  prediction,
  explanation,
}: {
  prediction: M3Prediction
  explanation: MlExplanationResult
}) {
  const item = (explanation.explanations as MlM3Explanation[])[0]
  if (!item) {
    return (
      <p className="text-sm text-muted-foreground">
        {prediction.prediction_count === 0
          ? "Your risk outlook will appear once your academic records are complete."
          : "The risk prediction is not available yet."}
      </p>
    )
  }

  const atRisk = item.risk_label === 1
  return (
    <div className="flex flex-col gap-5">
      <div
        className={`rounded-xl border p-4 ${
          atRisk ? "border-chart-3/30 bg-chart-3/5" : "border-chart-2/30 bg-chart-2/5"
        }`}
      >
        <SectionLabel>Next-Semester Outlook</SectionLabel>
        <div className="mt-2 flex items-center gap-2.5">
          <span
            className={`flex size-9 shrink-0 items-center justify-center rounded-full ${
              atRisk ? "bg-chart-3/15" : "bg-chart-2/15"
            }`}
          >
            {atRisk ? (
              <AlertTriangle className="size-5 text-chart-3" aria-hidden="true" />
            ) : (
              <ShieldCheck className="size-5 text-chart-2" aria-hidden="true" />
            )}
          </span>
          <div className="min-w-0">
            <p className="text-xl font-semibold">{atRisk ? "At Risk" : "On Track"}</p>
            <p className="text-xs text-muted-foreground">
              {atRisk
                ? "An elevated chance of academic difficulty was identified for next semester."
                : "No elevated risk of academic difficulty was identified for next semester."}
            </p>
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <SectionLabel>Why This Result?</SectionLabel>
        <ReasonList factors={item.factors} />
      </div>

      <div className="flex flex-col gap-2.5">
        <SectionLabel>What It Means</SectionLabel>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {atRisk
            ? "Based on your current academic signals, there is a higher chance of academic difficulty next semester. Identifying this early gives you time to strengthen your preparation."
            : "Based on your current academic signals, you are not currently identified as being at risk of academic difficulty next semester."}
        </p>
      </div>

      {item.suggestions.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <SectionLabel>Recommended Actions</SectionLabel>
          <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {item.suggestions.map((suggestion, index) => (
              <li
                key={index}
                className="flex items-start gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2.5 text-sm"
              >
                <ArrowRight className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                <span>{suggestion}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {item.inputs.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <SectionLabel>Key Signals</SectionLabel>
          <SignalGrid inputs={item.inputs} />
        </div>
      )}
    </div>
  )
}

export function M3InsightsCard({ model }: { model: MlModelInsight }) {
  return (
    <ModelCard
      id="ml-insights-m3"
      icon={ShieldCheck}
      title="Next-Semester Risk Prediction"
      subtitle="An early view of factors that may affect your next-semester academic performance."
    >
      {!model.available ? (
        <InsightUnavailable model={model} />
      ) : (
        <M3Body
          prediction={model.prediction as M3Prediction}
          explanation={model.explanation}
        />
      )}
    </ModelCard>
  )
}
