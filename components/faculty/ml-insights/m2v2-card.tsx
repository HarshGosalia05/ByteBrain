import { GraduationCap, CircleAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { m2V2SgpaTone, type M2V2PredictionData } from "@/lib/m2v2-prediction"

import { ModelCard } from "@/components/student/ml-insights/model-card"

export function FacultyM2V2Card({ data }: { data: M2V2PredictionData }) {
  const {
    observation_semester,
    prediction_takes_effect_semester,
    predicted_next_semester_sgpa,
    predicted_next_semester_percentage,
  } = data

  const sgpa = predicted_next_semester_sgpa
  const attention =
    sgpa !== null && ["warning", "destructive"].includes(m2V2SgpaTone(sgpa))

  return (
    <ModelCard
      id="faculty-ml-insights-m2v2"
      icon={GraduationCap}
      title="Next-semester performance forecast (M2 V2)"
      subtitle="Predicted SGPA and percentage for the student's upcoming regular academic semester, based on their last completed semester."
      badge={<Badge variant="secondary">M2 V2 · Next semester</Badge>}
    >
      {data.readiness_status !== "READY" ||
      predicted_next_semester_sgpa === null ||
      predicted_next_semester_percentage === null ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-5"
        >
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-medium">No upcoming semester forecast</p>
            <p className="text-xs text-muted-foreground">
              {data.reason ??
                "This student currently has no upcoming regular academic semester to forecast."}{" "}
              This prediction applies only when a next regular semester is ahead of the student.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-2">
            {attention && <Badge variant="warning">Needs attention</Badge>}
            <Badge variant="secondary">
              Semester {prediction_takes_effect_semester}
            </Badge>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-foreground/10 bg-background/40 px-3 py-3">
              <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                Predicted SGPA · Semester {prediction_takes_effect_semester}
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">
                {predicted_next_semester_sgpa.toFixed(2)}
                <span className="text-sm font-normal text-muted-foreground"> / 10</span>
              </p>
            </div>
            <div className="rounded-lg border border-foreground/10 bg-background/40 px-3 py-3">
              <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                Predicted Percentage · Semester {prediction_takes_effect_semester}
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">
                {predicted_next_semester_percentage.toFixed(1)}%
              </p>
            </div>
          </div>

          <div className="rounded-lg border border-foreground/10 bg-background/40 px-3 py-3">
            <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
              How to read this
            </p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              This is the model's estimate for the next regular semester
              {prediction_takes_effect_semester !== null
                ? ` (Semester ${prediction_takes_effect_semester})`
                : ""}
              , based on the student's completed
              {observation_semester !== null ? ` Semester ${observation_semester}` : " academic history"}
              . It is not their current semester result and not a guarantee.
            </p>
          </div>

          <p className="text-xs text-muted-foreground">
            {data.note} Model version {data.model_version}.
          </p>
        </div>
      )}
    </ModelCard>
  )
}