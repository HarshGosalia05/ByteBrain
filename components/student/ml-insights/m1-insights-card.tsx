import { BookOpen } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type {
  MlExplanationResult,
  MlM1Explanation,
  MlModelInsight,
  MlPredictionResult,
} from "@/lib/student-api"

import { FactorList } from "./factor-list"
import { InputDetails } from "./input-details"
import { InsightUnavailable } from "./insight-unavailable"
import { ModelCard } from "./model-card"

type M1Prediction = Extract<MlPredictionResult, { model_id: "m1" }>

function bandVariant(band: string): "success" | "secondary" | "warning" | "destructive" {
  if (band === "Top Performer" || band === "Above Average") return "success"
  if (band === "Average") return "secondary"
  if (band === "Below Average") return "warning"
  return "destructive"
}

function SubjectRow({ item }: { item: MlM1Explanation }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{item.subject_name ?? item.subject_id}</p>
          <p className="text-xs text-muted-foreground">Semester {item.semester_no}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {item.clipped && <Badge variant="warning">Adjusted to scale</Badge>}
          {item.projected_band === null ? (
            <Badge variant="muted">No band</Badge>
          ) : (
            <Badge variant={bandVariant(item.projected_band)}>{item.projected_band}</Badge>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-6">
        <div>
          <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
            Predicted end-sem marks
          </p>
          <p className="text-2xl font-semibold tabular-nums">
            {item.predicted_end_sem_marks.toFixed(1)}
            <span className="text-sm font-normal text-muted-foreground"> / 70</span>
          </p>
        </div>
        {item.projected_percentage !== null && (
          <div>
            <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
              Projected percentage
            </p>
            <p className="text-2xl font-semibold tabular-nums">{item.projected_percentage.toFixed(1)}%</p>
          </div>
        )}
      </div>

      <p className="mt-3 text-sm text-muted-foreground">{item.interpretation}</p>
      <div className="mt-3 flex flex-col gap-3">
        <FactorList factors={item.factors} />
        <InputDetails inputs={item.inputs} />
      </div>
    </div>
  )
}

function M1Body({
  prediction,
  explanation,
}: {
  prediction: M1Prediction
  explanation: MlExplanationResult
}) {
  const items = explanation.explanations as MlM1Explanation[]
  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => (
        <SubjectRow key={item.subject_id} item={item} />
      ))}
      {items.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {prediction.prediction_count} subject prediction{`${prediction.prediction_count === 1 ? "" : "s"}`} recorded
          for this student.
        </p>
      )}
    </div>
  )
}

export function M1InsightsCard({ model }: { model: MlModelInsight }) {
  return (
    <ModelCard
      id="ml-insights-m1"
      icon={BookOpen}
      title="Subject end-semester predictions"
      subtitle="Predicted marks on the 0–70 scale and the projected band for each subject."
      badge={<Badge variant="secondary">M1 · Subjects</Badge>}
    >
      {!model.available ? (
        <InsightUnavailable model={model} />
      ) : (
        <M1Body
          prediction={model.prediction as M1Prediction}
          explanation={model.explanation}
        />
      )}
    </ModelCard>
  )
}
