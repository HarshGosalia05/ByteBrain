import { AlertTriangle, ArrowRight, ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { FactorList } from "@/components/student/ml-insights/factor-list"
import { InputDetails } from "@/components/student/ml-insights/input-details"
import { ModelCard } from "@/components/student/ml-insights/model-card"
import type {
  FacultyMlExplanationResult,
  FacultyMlM3Explanation,
  FacultyMlModelInsight,
  FacultyMlPredictionResult,
} from "@/lib/faculty-api"

import { InsightUnavailable } from "./insight-unavailable"
import { M3FacultyReview } from "./m3-faculty-review"

type M3Prediction = Extract<FacultyMlPredictionResult, { model_id: "m3" }>

function M3Body({
  prediction,
  explanation,
}: {
  prediction: M3Prediction
  explanation: FacultyMlExplanationResult
}) {
  const item = (explanation.explanations as FacultyMlM3Explanation[])[0]
  if (!item) {
    return (
      <p className="text-sm text-muted-foreground">
        {prediction.prediction_count === 0
          ? "No future-risk prediction recorded yet."
          : "The future-risk prediction is not available yet."}
      </p>
    )
  }
  const atRisk = item.risk_label === 1
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/40 px-3 py-3">
        <Badge variant="warning">Future risk prediction</Badge>
        <p className="text-xs text-muted-foreground">
          A model-based view of next semester — separate from the deterministic risk register
          (risk_predictions) and not a guaranteed outcome.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {atRisk ? (
          <>
            <Badge variant="warning">
              <AlertTriangle aria-hidden="true" />
              Possible difficulty
            </Badge>
            <p className="text-sm text-muted-foreground">
              The model flags a higher chance of at-risk status next semester. Early academic
              support can change this outcome.
            </p>
          </>
        ) : (
          <>
            <Badge variant="success">
              <ShieldCheck aria-hidden="true" />
              On track
            </Badge>
            <p className="text-sm text-muted-foreground">
              The model does not currently flag at-risk status for next semester.
            </p>
          </>
        )}
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

      {item.suggestions.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-[0.6875rem] font-semibold tracking-widest text-muted-foreground uppercase">
            Recommended action
          </p>
          <ul className="flex flex-col gap-1.5">
            {item.suggestions.map((suggestion, index) => (
              <li key={index} className="flex items-start gap-2 text-sm">
                <ArrowRight className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                <span>{suggestion}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <InputDetails inputs={item.inputs} />
    </div>
  )
}

export function M3InsightsCard({
  model,
  studentId,
}: {
  model: FacultyMlModelInsight
  studentId: string
}) {
  return (
    <ModelCard
      id="faculty-ml-insights-m3"
      icon={AlertTriangle}
      title="Next-semester risk prediction"
      subtitle="A future-risk model prediction with the signals behind it and grounded next steps for support."
      badge={<Badge variant="warning">M3 · Future risk</Badge>}
    >
      {!model.available ? (
        <InsightUnavailable model={model} />
      ) : (
        <div className="flex flex-col gap-4">
          <M3Body
            prediction={model.prediction as M3Prediction}
            explanation={model.explanation}
          />
          <M3FacultyReview studentId={studentId} />
        </div>
      )}
    </ModelCard>
  )
}
