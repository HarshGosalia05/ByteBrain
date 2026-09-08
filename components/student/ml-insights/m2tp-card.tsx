import { BookOpen, FlaskConical, GraduationCap, Info } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  m2tpPerformanceTone,
  type M2TPPredictionData,
  type M2TPSubjectTypePrediction,
} from "@/lib/m2tp-prediction"

import { ModelCard } from "./model-card"

type Props = {
  data: M2TPPredictionData | null
  reason?: string | null
}

export function M2TPCard({ data, reason = null }: Props) {
  if (data === null || data.readiness_status === "NO_DATA") {
    return <M2TPUnavailableCard reason={reason ?? data?.reason ?? null} />
  }

  const { observation_semester, target_semester, theory, practical } = data

  return (
    <ModelCard
      id="ml-insights-m2tp"
      icon={GraduationCap}
      title="Next-Semester Performance"
      subtitle="Predicted academic performance for your upcoming regular semester across Theory and Practical coursework."
      badge={<Badge variant="secondary">M2-TP · Next semester</Badge>}
    >
      <div className="flex flex-col gap-5">
        {/* Semester Context Header */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-foreground/10 pb-3 text-xs text-muted-foreground">
          <span>
            {observation_semester !== null && target_semester !== null ? (
              <>
                Observation history up to <strong>Semester {observation_semester}</strong> → Forecast for{" "}
                <strong className="text-foreground">Semester {target_semester}</strong>
              </>
            ) : (
              "Next regular semester performance forecast"
            )}
          </span>
          {data.model_version && (
            <span className="text-[0.6875rem]">Model {data.model_version}</span>
          )}
        </div>

        {/* Theory & Practical Prediction Panels */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {/* Theory Panel */}
          <SubjectTypePanel
            icon={BookOpen}
            title="Theory"
            prediction={theory}
            targetSemester={target_semester}
          />

          {/* Practical Panel */}
          <SubjectTypePanel
            icon={FlaskConical}
            title="Practical"
            prediction={practical}
            targetSemester={target_semester}
          />
        </div>

        {/* Note / Scope footer */}
        <div className="rounded-lg border border-foreground/10 bg-background/40 px-3.5 py-3 text-xs leading-relaxed text-muted-foreground">
          <p>
            <strong>Scope & Methodology:</strong> Theory and Practical performance are predicted independently using dedicated ML pipelines trained strictly on pre-semester academic data. Predictions apply only to upcoming regular semesters.
          </p>
        </div>
      </div>
    </ModelCard>
  )
}

function SubjectTypePanel({
  icon: Icon,
  title,
  prediction,
  targetSemester,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: "Theory" | "Practical"
  prediction: M2TPSubjectTypePrediction
  targetSemester: number | null
}) {
  const isReady =
    prediction.readiness_status === "READY" &&
    prediction.predicted_percentage !== null

  return (
    <div className="flex flex-col justify-between rounded-lg border border-foreground/10 bg-background/40 p-4 transition-colors">
      <div className="flex flex-col gap-3">
        {/* Panel Header */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-md bg-foreground/5 text-foreground">
              <Icon className="size-4" />
            </div>
            <h4 className="text-sm font-semibold tracking-tight">{title}</h4>
          </div>
          {isReady ? (
            <Badge variant={m2tpPerformanceTone(prediction.predicted_percentage)}>
              {prediction.predicted_percentage! >= 75
                ? "Strong"
                : prediction.predicted_percentage! >= 60
                  ? "Moderate"
                  : "Needs Attention"}
            </Badge>
          ) : (
            <Badge variant="outline">Unavailable</Badge>
          )}
        </div>

        {/* Predicted Performance Body */}
        {isReady ? (
          <div className="my-1 flex flex-col gap-1">
            <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
              Predicted Performance
            </p>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-bold tracking-tight tabular-nums text-foreground">
                {prediction.predicted_percentage!.toFixed(1)}%
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Estimated marks in Semester {targetSemester ?? "ahead"} {title.toLowerCase()} coursework.
            </p>
          </div>
        ) : (
          <div className="my-2 rounded-md border border-dashed border-border px-3 py-3 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">No forecast available</p>
            <p className="mt-0.5 leading-relaxed">
              {prediction.reason ??
                `No upcoming regular ${title.toLowerCase()} coursework is scheduled.`}
            </p>
          </div>
        )}
      </div>

      {/* Metadata / Course count */}
      <div className="mt-3 border-t border-foreground/5 pt-2 text-[0.6875rem] text-muted-foreground">
        {isReady && prediction.target_subject_count > 0 ? (
          <span>{prediction.target_subject_count} {title.toLowerCase()} course{prediction.target_subject_count > 1 ? "s" : ""} scheduled</span>
        ) : (
          <span>0 courses scheduled</span>
        )}
        {prediction.algorithm && (
          <span className="ml-1 text-muted-foreground/60">· {prediction.algorithm}</span>
        )}
      </div>
    </div>
  )
}

function M2TPUnavailableCard({ reason }: { reason: string | null }) {
  return (
    <ModelCard
      id="ml-insights-m2tp"
      icon={GraduationCap}
      title="Next-Semester Performance"
      subtitle="AI-estimated academic performance for your upcoming regular semester across Theory and Practical coursework."
      badge={<Badge variant="secondary">M2-TP · Next semester</Badge>}
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
              "There is no upcoming normal academic semester with regular Theory or Practical coursework at your current academic stage (e.g. final internship semester)."}{" "}
            This is an informational state, not an error.
          </p>
        </div>
      </div>
    </ModelCard>
  )
}
