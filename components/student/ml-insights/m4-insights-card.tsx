import { AlertTriangle, CheckCircle2, Target } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type {
  MlExplanationResult,
  MlM4Explanation,
  MlModelInsight,
  MlPredictionResult,
} from "@/lib/student-api"

import { InsightUnavailable } from "./insight-unavailable"
import { ModelCard } from "./model-card"

type M4Prediction = Extract<MlPredictionResult, { model_id: "m4" }>

type LevelTone = "success" | "warning" | "destructive"

function levelTone(level: string): LevelTone {
  if (level.toLowerCase() === "high") return "success"
  if (level.toLowerCase() === "medium") return "warning"
  return "destructive"
}

const TONE_FILL: Record<LevelTone, string> = {
  success: "bg-chart-2",
  warning: "bg-chart-3",
  destructive: "bg-destructive",
}

function ScoreMeter({ score, tone }: { score: number; tone: LevelTone }) {
  const clamped = Math.max(0, Math.min(100, score))
  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full bg-muted"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      aria-label="Career readiness progress"
    >
      <div
        className={`h-full rounded-full ${TONE_FILL[tone]} transition-[width]`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}

function FactorList({
  title,
  items,
  positive,
}: {
  title: string
  items: string[]
  positive: boolean
}) {
  const Icon = positive ? CheckCircle2 : AlertTriangle
  const toneClass = positive ? "text-chart-2" : "text-chart-3"
  return (
    <div className="min-w-0 rounded-lg border border-foreground/10 bg-background/40 p-3.5">
      <p className="flex items-center gap-1.5 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
        <Icon className={`size-3.5 ${toneClass}`} aria-hidden="true" />
        {title}
      </p>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">
          {positive
            ? "Your strengths will appear here as your results are recorded."
            : "Nothing needs attention right now."}
        </p>
      ) : (
        <ul className="mt-2.5 flex flex-col gap-1.5">
          {items.map((factor, index) => (
            <li key={index} className="flex items-start gap-2 text-sm">
              <Icon
                className={`mt-0.5 size-4 shrink-0 ${toneClass}`}
                aria-hidden="true"
              />
              <span>{factor}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function M4Body({
  prediction,
  explanation,
}: {
  prediction: M4Prediction
  explanation: MlExplanationResult
}) {
  const item = (explanation.explanations as MlM4Explanation[])[0]
  if (!item) {
    return (
      <p className="text-sm text-muted-foreground">
        {prediction.prediction_count === 0
          ? "Your readiness score will appear once your academic records are complete."
          : "Your readiness score is not available yet."}
      </p>
    )
  }
  const tone = levelTone(item.readiness_level)
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-baseline gap-1.5">
            <span className="text-5xl font-semibold tabular-nums">
              {item.readiness_score.toFixed(1)}
            </span>
            <span className="pb-1 text-sm text-muted-foreground">/ 100</span>
          </div>
          <Badge variant={tone} className="px-3 py-1 text-sm">
            {item.readiness_level}
          </Badge>
        </div>
        <ScoreMeter score={item.readiness_score} tone={tone} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <FactorList title="Strengths" items={item.positive_factors} positive />
        <FactorList
          title="Areas to improve"
          items={item.risk_factors}
          positive={false}
        />
      </div>
    </div>
  )
}

export function M4InsightsCard({ model }: { model: MlModelInsight }) {
  return (
    <ModelCard
      id="ml-insights-m4"
      icon={Target}
      title="Career Readiness"
      subtitle="Your current preparation level for your chosen career direction."
    >
      {!model.available ? (
        <InsightUnavailable model={model} />
      ) : (
        <M4Body
          prediction={model.prediction as M4Prediction}
          explanation={model.explanation}
        />
      )}
    </ModelCard>
  )
}
