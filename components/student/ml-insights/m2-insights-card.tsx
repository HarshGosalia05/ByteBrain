import {
  ArrowDownRight,
  ArrowUpRight,
  Minus,
  TrendingUp,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type {
  MlExplanationResult,
  MlM2Explanation,
  MlModelInsight,
  MlPredictionResult,
} from "@/lib/student-api"

import { InsightUnavailable } from "./insight-unavailable"
import { ModelCard } from "./model-card"
import { SectionLabel, SignalGrid } from "./signal-list"

type M2Prediction = Extract<MlPredictionResult, { model_id: "m2" }>

type Trend = "improving" | "stable" | "declining"

const TREND_EPSILON = 0.05

function classifyTrend(delta: number | null): Trend | null {
  if (delta === null) return null
  if (delta > TREND_EPSILON) return "improving"
  if (delta < -TREND_EPSILON) return "declining"
  return "stable"
}

const trendMeta: Record<
  Trend,
  {
    label: string
    Icon: typeof ArrowUpRight
    className: string
    meaning: (predPct: string) => string
    outlookBadge: "success" | "muted" | "warning"
    outlookTitle: string
    outlookMessage: string
  }
> = {
  improving: {
    label: "Improving",
    Icon: ArrowUpRight,
    className: "text-chart-2",
    meaning: (p) =>
      `Your predicted performance for the coming semester is ${p}, which is higher than your current semester performance.`,
    outlookBadge: "success",
    outlookTitle: "Positive",
    outlookMessage:
      "Your predicted performance is trending upward. Continue your current study consistency.",
  },
  stable: {
    label: "Stable",
    Icon: Minus,
    className: "text-muted-foreground",
    meaning: (p) =>
      `Your predicted performance for the coming semester is ${p}, broadly aligned with your current level.`,
    outlookBadge: "muted",
    outlookTitle: "Stable",
    outlookMessage:
      "Your predicted performance is broadly aligned with your current level. Focus on consistency.",
  },
  declining: {
    label: "Needs attention",
    Icon: ArrowDownRight,
    className: "text-chart-3",
    meaning: (p) =>
      `Your predicted performance for the coming semester is ${p}, which is lower than your current semester performance.`,
    outlookBadge: "warning",
    outlookTitle: "Needs Attention",
    outlookMessage:
      "Your predicted performance is below your current level. Consider strengthening preparation before the next semester.",
  },
}

function MetricCard({
  label,
  value,
  children,
}: {
  label: string
  value?: string
  children?: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-foreground/10 bg-background/40 px-3 py-3">
      <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {children}
    </div>
  )
}

function M2Body({
  prediction,
  explanation,
}: {
  prediction: M2Prediction
  explanation: MlExplanationResult
}) {
  const item = (explanation.explanations as MlM2Explanation[])[0]
  if (!item) {
    return (
      <p className="text-sm text-muted-foreground">
        {prediction.prediction_count === 0
          ? "Your next-semester prediction will appear once your academic records are complete."
          : "The next-semester prediction is not available yet."}
      </p>
    )
  }

  const predPct = `${item.predicted_next_semester_percentage.toFixed(1)}%`
  const delta = item.projected_delta_percentage
  const trend = classifyTrend(delta)
  const trendInfo = trend ? trendMeta[trend] : null

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <MetricCard
          label="Predicted SGPA"
          value={item.predicted_next_semester_sgpa.toFixed(2)}
        />
        <MetricCard label="Predicted Percentage" value={predPct} />
        <MetricCard
          label="Compared with Current"
          value={
            item.current_percentage === null
              ? "—"
              : `${item.current_percentage.toFixed(1)}%`
          }
        >
          {trendInfo && delta !== null && (
            <span
              className={`mt-1 flex items-center gap-1 text-xs font-medium tabular-nums ${trendInfo.className}`}
            >
              <trendInfo.Icon className="size-3.5 shrink-0" aria-hidden="true" />
              {`${delta >= 0 ? "+" : ""}${delta.toFixed(2)} points · ${trendInfo.label}`}
            </span>
          )}
        </MetricCard>
      </div>

      <div className="flex flex-col gap-2.5">
        <SectionLabel>What This Means</SectionLabel>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {trendInfo && item.current_percentage !== null
            ? trendInfo.meaning(predPct)
            : `Your predicted performance for the coming semester is ${predPct}. Your current-semester comparison will appear once results are recorded.`}
        </p>
      </div>

      {item.inputs.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <SectionLabel>Key Signals</SectionLabel>
          <SignalGrid inputs={item.inputs} />
        </div>
      )}

      {trendInfo && (
        <div className="flex flex-col gap-2.5">
          <SectionLabel>Academic Outlook</SectionLabel>
          <div className="flex flex-col gap-2 rounded-xl border border-foreground/10 bg-background/40 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2.5">
              <Badge variant={trendInfo.outlookBadge}>{trendInfo.outlookTitle}</Badge>
              <p className="text-sm font-medium">{trendInfo.label}</p>
            </div>
            <p className="text-sm text-muted-foreground sm:max-w-md sm:text-right">
              {trendInfo.outlookMessage}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export function M2InsightsCard({ model }: { model: MlModelInsight }) {
  return (
    <ModelCard
      id="ml-insights-m2"
      icon={TrendingUp}
      title="Next-Semester Performance"
      subtitle="Your predicted academic performance for the coming semester."
    >
      {!model.available ? (
        <InsightUnavailable model={model} />
      ) : (
        <M2Body
          prediction={model.prediction as M2Prediction}
          explanation={model.explanation}
        />
      )}
    </ModelCard>
  )
}
