import { GraduationCap, CircleAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { m2V2SgpaTone, type M2V2PredictionData } from "@/lib/m2v2-prediction"

import { ModelCard } from "./model-card"

export function M2V2Card({ data }: { data: M2V2PredictionData }) {
  const {
    observation_semester,
    prediction_takes_effect_semester,
    predicted_next_semester_sgpa,
    predicted_next_semester_percentage,
  } = data

  return (
    <ModelCard
      id="ml-insights-m2v2"
      icon={GraduationCap}
      title="Next-semester performance forecast (M2 V2)"
      subtitle="Your predicted SGPA and percentage for the upcoming regular academic semester, based on your last completed semester."
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
            <p className="text-sm font-medium">No upcoming semester forecast yet</p>
            <p className="text-xs text-muted-foreground">
              {data.reason ??
                "You currently have no upcoming regular academic semester to forecast."}{" "}
              This prediction applies only when a next regular semester is ahead of you.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-foreground/10 bg-background/40 px-3 py-3">
              <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                Predicted SGPA · Semester {prediction_takes_effect_semester}
              </p>
              <div className="mt-1 flex items-center gap-2">
                <p className="text-2xl font-semibold tabular-nums">
                  {predicted_next_semester_sgpa.toFixed(2)}
                </p>
                <Badge variant={m2V2SgpaTone(predicted_next_semester_sgpa)}>out of 10</Badge>
              </div>
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
              What this means
            </p>
            <p className="mt-1 text-sm leading-relaxed">
              {observation_semester !== null && prediction_takes_effect_semester !== null
                ? `Based on your academic history up to Semester ${observation_semester}, the model estimates your performance in Semester ${prediction_takes_effect_semester} around this level.`
                : "Based on your academic history up to the current semester, the model estimates your next-semester performance around this level."}
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