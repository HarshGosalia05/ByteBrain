import { BookOpen, CircleAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  m1V2GradeTone,
  type M1V2PredictionData,
  type M1V2SubjectPrediction,
} from "@/lib/m1v2-prediction"

import { ModelCard } from "@/components/student/ml-insights/model-card"

function SubjectRow({ item }: { item: M1V2SubjectPrediction }) {
  const band = item.grade_band.trim().toUpperCase()
  const attention = band === "F" || band === "C"
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{item.subject_id}</p>
          <p className="text-xs text-muted-foreground">Semester {item.semester_no}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {attention && <Badge variant="warning">Needs attention</Badge>}
          <Badge variant={m1V2GradeTone(item.grade_band)}>{item.grade_band}</Badge>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-6">
        <div>
          <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
            Predicted end-sem marks
          </p>
          <p className="text-2xl font-semibold tabular-nums">
            {item.predicted_end_sem_marks.toFixed(1)}
            <span className="text-sm font-normal text-muted-foreground">
              {" "}/ {item.target_max}
            </span>
          </p>
        </div>
        {item.input_features.att_total_pct !== null && (
          <div>
            <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
              Attendance
            </p>
            <p className="text-2xl font-semibold tabular-nums">
              {item.input_features.att_total_pct.toFixed(1)}%
            </p>
          </div>
        )}
        {item.input_features.pre_endsem_assessment_pct !== null && (
          <div>
            <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
              Pre-end-sem assessment
            </p>
            <p className="text-2xl font-semibold tabular-nums">
              {item.input_features.pre_endsem_assessment_pct.toFixed(1)}%
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export function FacultyM1V2Card({ data }: { data: M1V2PredictionData }) {
  return (
    <ModelCard
      id="faculty-ml-insights-m1v2"
      icon={BookOpen}
      title="Subject end-semester predictions (M1 V2)"
      subtitle="Predicted marks on the 0–70 scale with the projected grade band per subject, plus the student's own attendance and pre-end-sem assessment signals."
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
        <div className="flex flex-col gap-3">
          {data.subjects.map((item) => (
            <SubjectRow key={item.subject_id} item={item} />
          ))}
          <p className="text-xs text-muted-foreground">
            {data.note ??
              "Predicted end-sem marks are model estimates, not actual results. Uncertainty is unavailable for this model."}{" "}
            Model version {data.model_version}.
          </p>
        </div>
      )}
    </ModelCard>
  )
}
