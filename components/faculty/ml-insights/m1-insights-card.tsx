import { BookOpen } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { FactorList } from "@/components/student/ml-insights/factor-list"
import { InputDetails } from "@/components/student/ml-insights/input-details"
import { ModelCard } from "@/components/student/ml-insights/model-card"
import {
  facultyMlBandTone,
  type FacultyMlExplanationResult,
  type FacultyMlM1Explanation,
  type FacultyMlModelInsight,
  type FacultyMlPredictionResult,
} from "@/lib/faculty-api"

import { InsightUnavailable } from "./insight-unavailable"

type M1Prediction = Extract<FacultyMlPredictionResult, { model_id: "m1" }>

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[0.6875rem] font-semibold tracking-widest text-muted-foreground uppercase">
      {children}
    </p>
  )
}

function SubjectRow({ item }: { item: FacultyMlM1Explanation }) {
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
            <Badge variant={facultyMlBandTone(item.projected_band)}>{item.projected_band}</Badge>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-6">
        <div>
          <SectionLabel>Predicted end-sem marks</SectionLabel>
          <p className="text-2xl font-semibold tabular-nums">
            {item.predicted_end_sem_marks.toFixed(1)}
            <span className="text-sm font-normal text-muted-foreground"> / 70</span>
          </p>
        </div>
        {item.projected_percentage !== null && (
          <div>
            <SectionLabel>Projected percentage</SectionLabel>
            <p className="text-2xl font-semibold tabular-nums">
              {item.projected_percentage.toFixed(1)}%
            </p>
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-col gap-2">
        <SectionLabel>Why</SectionLabel>
        <FactorList factors={item.factors} />
      </div>

      <div className="mt-4 flex flex-col gap-2">
        <SectionLabel>What it means</SectionLabel>
        <p className="text-sm text-muted-foreground">{item.interpretation}</p>
      </div>

      <div className="mt-3">
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
  explanation: FacultyMlExplanationResult
}) {
  const items = explanation.explanations as FacultyMlM1Explanation[]
  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => (
        <SubjectRow key={item.subject_id} item={item} />
      ))}
      {items.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {prediction.prediction_count} subject prediction
          {`${prediction.prediction_count === 1 ? "" : "s"}`} recorded for this student, but the
          detailed explanation is not available yet.
        </p>
      )}
    </div>
  )
}

export function M1InsightsCard({ model }: { model: FacultyMlModelInsight }) {
  return (
    <ModelCard
      id="faculty-ml-insights-m1"
      icon={BookOpen}
      title="Subject end-semester predictions"
      subtitle="Predicted marks on the 0–70 scale with the projected band, plus the inputs and rules behind each estimate."
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
