import { CircleAlert, ShieldAlert } from "lucide-react"

import type { FacultyMlModelInsight } from "@/lib/faculty-api"

export function InsightUnavailable({
  model,
}: {
  model: Extract<FacultyMlModelInsight, { available: false }>
}) {
  const blocked = model.reason === "blocked"
  const message =
    model.reason === "no_data"
      ? "More academic records are needed before this prediction can be generated."
      : blocked
        ? "This prediction is not currently shown because the model's validation gate has not been satisfied."
        : "This insight is temporarily unavailable. Please check back later."
  return (
    <div
      role="status"
      className={`flex items-start gap-3 rounded-lg border px-4 py-5 ${
        blocked ? "border-dashed border-chart-3/40 bg-chart-3/5" : "border-dashed"
      }`}
    >
      {blocked ? (
        <ShieldAlert className="mt-0.5 size-4 shrink-0 text-chart-3" aria-hidden="true" />
      ) : (
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      )}
      <div className="flex flex-col gap-0.5">
        <p className="text-sm font-medium">
          {blocked ? "Model unavailable" : "Not available yet"}
        </p>
        <p className="text-xs text-muted-foreground">{message}</p>
      </div>
    </div>
  )
}
