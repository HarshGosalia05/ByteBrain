import { TriangleAlert, CircleAlert, ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  m3V2RiskTone,
  formatRiskPercent,
  riskLevelLabel,
  m3V2FeatureLabel,
  m3V2SignalValue,
  type M3V2PredictionData,
} from "@/lib/m3v2-prediction"

import { ModelCard } from "@/components/student/ml-insights/model-card"

export function FacultyM3V2Card({ data }: { data: M3V2PredictionData }) {
  const {
    probability_at_risk,
    is_estimated_at_risk,
    threshold,
    signals,
  } = data

  const tone = m3V2RiskTone(probability_at_risk)
  const atRisk = is_estimated_at_risk === true
  const attention =
    atRisk || (probability_at_risk !== null && ["warning", "destructive"].includes(tone))
  const ready = data.readiness_status === "READY" && probability_at_risk !== null

  return (
    <ModelCard
      id="faculty-ml-insights-m3v2"
      icon={TriangleAlert}
      title="Academic risk estimate (M3 V2)"
      subtitle="Estimated probability this student enters an academic-risk state (backlog/ATKT) based on their latest completed academic data."
      badge={<Badge variant="secondary">M3 V2 · Risk estimate</Badge>}
    >
      {!ready ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-5"
        >
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-medium">No at-risk estimate</p>
            <p className="text-xs text-muted-foreground">
              {data.reason ??
                "This student currently has insufficient historical academic data to evaluate academic risk."}{" "}
              This estimate is based on the student's latest completed academic records.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-2">
            {attention && <Badge variant="warning">Needs attention</Badge>}
            <Badge variant="secondary">Based on latest completed data</Badge>
          </div>

          <div className="rounded-lg border border-foreground/10 bg-background/40 px-4 py-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                  Estimated academic risk
                </p>
                <div className="mt-1 flex items-baseline gap-2">
                  <p className="text-5xl font-bold tabular-nums">
                    {formatRiskPercent(probability_at_risk)}
                  </p>
                  <Badge variant={tone}>{riskLevelLabel(probability_at_risk)}</Badge>
                </div>
                <p className="mt-1 text-sm font-normal text-muted-foreground">
                  · threshold {formatRiskPercent(threshold)}
                </p>
              </div>
              <div className="max-w-xs">
                <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                  Interpretation
                </p>
                <div className="mt-1 flex items-start gap-2">
                  <ShieldCheck className="mt-0.5 size-4 shrink-0 text-foreground/60" aria-hidden="true" />
                  <p className="text-sm">
                    {atRisk
                      ? "Model signals point to an elevated risk of an academic setback based on latest records."
                      : "Model signals currently point to a low estimated risk."}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {signals.length > 0 && (
            <div>
              <p className="mb-2 text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                Signals contributing to this estimate
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
                These are the top factors the model weighed for this estimate. A signal shows
                &ldquo;Not available&rdquo; when the underlying source record is not recorded for this student.
              </p>
            </div>
          )}

          <p className="text-xs text-muted-foreground">
            {data.note} Model version {data.model_version}. An estimate is not a diagnosis.
          </p>
        </div>
      )}
    </ModelCard>
  )
}