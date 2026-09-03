import { TriangleAlert, CircleAlert, ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { m3V2RiskTone, formatRiskPercent, riskLevelLabel, type M3V2PredictionData } from "@/lib/m3v2-prediction"

import { ModelCard } from "@/components/student/ml-insights/model-card"

export function FacultyM3V2Card({ data }: { data: M3V2PredictionData }) {
  const {
    probability_at_risk,
    is_estimated_at_risk,
    prediction_takes_effect_semester,
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
      subtitle="Estimated probability this student enters an academic-risk state (backlog/ATKT) in the next regular semester, based on their last completed semester."
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
                "This student currently has no upcoming regular academic semester to estimate risk for."}{" "}
              This estimate applies only when a next regular semester is ahead of the student.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-2">
            {attention && <Badge variant="warning">Needs attention</Badge>}
            <Badge variant="secondary">Semester {prediction_takes_effect_semester}</Badge>
          </div>

          <div className="rounded-lg border border-foreground/10 bg-background/40 px-4 py-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[0.6875rem] font-medium tracking-widest text-muted-foreground uppercase">
                  Estimated risk
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
                      ? "Model signal points to an elevated risk of an academic setback next semester."
                      : "Model signal currently points to a low estimated risk."}
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
                {signals.slice(0, 5).map((s) => (
                  <li
                    key={s.feature}
                    className="flex items-center justify-between rounded-md border border-foreground/10 bg-background/40 px-3 py-2 text-xs"
                  >
                    <span className="font-medium">{s.feature}</span>
                    <span className="tabular-nums text-muted-foreground">
                      {s.raw_value !== null && s.raw_value !== undefined
                        ? Number(s.raw_value).toFixed(2)
                        : "—"}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[0.6875rem] text-muted-foreground">
                These are the factors the model weighed most for this estimate.
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