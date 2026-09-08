import { TriangleAlert, CircleAlert, Info, ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { m3V2RiskTone, riskLevelLabel, formatRiskPercent, m3V2FeatureLabel, m3V2SignalValue, type M3V2PredictionData } from "@/lib/m3v2-prediction"

import { ModelCard } from "./model-card"

type Props = ({ data: M3V2PredictionData } | { data: null; reason?: string | null }) & {
  reason?: string | null
}

export function M3V2Card(props: Props) {
  const { data } = props
  if (data === null) {
    return (
      <M3V2UnavailableCard reason={props.reason ?? null} />
    )
  }

  const {
    probability_at_risk,
    is_estimated_at_risk,
    prediction_takes_effect_semester,
    threshold,
    signals,
  } = data

  const tone = m3V2RiskTone(probability_at_risk)
  const atRisk = is_estimated_at_risk === true
  const ready = data.readiness_status === "READY" && probability_at_risk !== null

  return (
    <ModelCard
      id="ml-insights-m3v2"
      icon={TriangleAlert}
      title="Academic Risk Assessment"
      subtitle="Estimated probability of entering an academic-risk state (backlog/ATKT) based on your latest completed academic data."
      badge={<Badge variant="secondary">M3 · Risk assessment</Badge>}
    >
      {!ready ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-5"
        >
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-medium">No at-risk estimate yet</p>
            <p className="text-xs text-muted-foreground">
              {data.reason ??
                "Insufficient historical academic data is available to evaluate academic risk."}{" "}
              This estimate is based on your latest completed academic records.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="rounded-lg border border-foreground/10 bg-background/40 px-4 py-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                  Estimated academic risk · Based on latest completed academic data
                </p>
                <div className="mt-1 flex items-baseline gap-2">
                  <p className="text-5xl font-bold tabular-nums">{formatRiskPercent(probability_at_risk)}</p>
                  <Badge variant={tone}>{riskLevelLabel(probability_at_risk)}</Badge>
                </div>
                <p className="mt-1 text-[0.6875rem] text-muted-foreground">
                  Decision threshold {formatRiskPercent(threshold)}
                </p>
              </div>
              <div className="max-w-xs">
                <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                  Interpretation
                </p>
                <div className="mt-1 flex items-start gap-2">
                  <ShieldCheck
                    className={`mt-0.5 size-4 shrink-0 ${atRisk ? "text-destructive" : "text-foreground/60"}`}
                    aria-hidden="true"
                  />
                  <p className="text-sm">
                    {atRisk
                      ? "Signals point to an elevated risk of an academic setback based on latest records."
                      : "Signals currently point to a low estimated risk of an academic setback."}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-foreground/10 bg-background/40 px-3 py-3">
              <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                Recommended next steps
              </p>
              <ul className="mt-1.5 flex list-disc flex-col gap-1 ps-4 text-sm">
                <li>Review any weak subjects before upcoming coursework.</li>
                <li>Aim to keep attendance consistent.</li>
                <li>Address any pending backlogs early.</li>
                <li>Maintain a steady study routine.</li>
              </ul>
              <p className="mt-2 text-[0.6875rem] text-muted-foreground">
                These are general suggestions based on the model&apos;s estimate — not a diagnosis.
              </p>
            </div>

            <div>
              <p className="mb-2 text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                Key signals used by the model
              </p>
              <ul className="flex flex-col gap-1.5">
                {signals.slice(0, 5).map((s) => {
                  const available = s.raw_value !== null && s.raw_value !== undefined && !Number.isNaN(s.raw_value)
                  return (
                    <li
                      key={s.feature}
                      className="flex items-center justify-between gap-3 rounded-md border border-foreground/10 bg-background/40 px-3 py-2 text-xs"
                    >
                      <span className="font-medium">{m3V2FeatureLabel(s.feature)}</span>
                      <span className={available ? "tabular-nums text-muted-foreground" : "text-muted-foreground italic"}>
                        {m3V2SignalValue(s)}
                      </span>
                    </li>
                  )
                })}
              </ul>
              <p className="mt-2 text-[0.6875rem] text-muted-foreground">
                These are the top factors the model weighed for this estimate. A signal shows&nbsp;
                &ldquo;Not available&rdquo; when the underlying record is not stored for your
                cohort — the estimate already accounts for it, so your risk level is not changed
                by that missing value. Factors are feature values the model used, not a guarantee.
              </p>
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            {data.note} Model version {data.model_version}. An estimate is not a diagnosis.
          </p>
        </div>
      )}
    </ModelCard>
  )
}

function M3V2UnavailableCard({ reason }: { reason: string | null }) {
  return (
    <ModelCard
      id="ml-insights-m3v2"
      icon={TriangleAlert}
      title="Academic Risk Assessment"
      subtitle="Estimated probability of entering an academic-risk state based on latest completed academic data."
      badge={<Badge variant="secondary">M3 · Risk assessment</Badge>}
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
              "An academic-risk estimate is currently unavailable because the required academic records are not yet present in the dataset."}{" "}
            This is an informational state, not an error.
          </p>
        </div>
      </div>
    </ModelCard>
  )
}