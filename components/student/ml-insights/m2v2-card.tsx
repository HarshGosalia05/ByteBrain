import { GraduationCap, CircleAlert, Info } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { m2V2SgpaTone, type M2V2PredictionData } from "@/lib/m2v2-prediction"

import { ModelCard } from "./model-card"

type Props = ({ data: M2V2PredictionData } | { data: null; reason?: string | null }) & {
  reason?: string | null
}

export function M2V2Card(props: Props) {
  const { data } = props
  if (data === null) {
    return (
      <M2V2UnavailableCard reason={props.reason ?? null} />
    )
  }

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
      title="Next-Semester Performance"
      subtitle="Your predicted SGPA and percentage for the upcoming regular academic semester, based on your last completed semester."
      badge={<Badge variant="secondary">M2 · Next semester</Badge>}
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
          <div className="rounded-lg border border-foreground/10 bg-background/40 px-4 py-5">
            <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
              Predicted next-semester SGPA · Semester {prediction_takes_effect_semester}
            </p>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-6 gap-y-2">
              <div className="flex items-baseline gap-2">
                <p className="text-5xl font-bold tabular-nums">{predicted_next_semester_sgpa.toFixed(2)}</p>
                <Badge variant={m2V2SgpaTone(predicted_next_semester_sgpa)}>out of 10</Badge>
              </div>
              <div>
                <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                  Predicted percentage
                </p>
                <p className="text-2xl font-semibold tabular-nums">{predicted_next_semester_percentage.toFixed(1)}%</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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
            <div className="rounded-lg border border-foreground/10 bg-background/40 px-3 py-3">
              <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                Scope
              </p>
              <p className="mt-1 text-sm leading-relaxed">
                This prediction applies only when a next regular semester is ahead of you.
              </p>
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            {data.note} Model version {data.model_version}.
          </p>
        </div>
      )}
    </ModelCard>
  )
}

function M2V2UnavailableCard({ reason }: { reason: string | null }) {
  return (
    <ModelCard
      id="ml-insights-m2v2"
      icon={GraduationCap}
      title="Next-Semester Performance"
      subtitle="AI-estimated academic performance for your upcoming normal semester."
      badge={<Badge variant="secondary">M2 · Next semester</Badge>}
    >
      <div
        role="status"
        className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-5"
      >
        <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium">Prediction unavailable</p>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {reason ??
              "There is no upcoming normal academic semester available for this prediction at your current academic stage."}{" "}
            This is an informational state, not an error.
          </p>
        </div>
      </div>
    </ModelCard>
  )
}