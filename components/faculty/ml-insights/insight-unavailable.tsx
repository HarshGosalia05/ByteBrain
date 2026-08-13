import { CircleAlert } from "lucide-react"

import type { FacultyMlModelInsight } from "@/lib/faculty-api"

export function InsightUnavailable({
  model,
}: {
  model: Extract<FacultyMlModelInsight, { available: false }>
}) {
  const message =
    model.reason === "no_data"
      ? "More academic records are needed before this prediction can be generated."
      : "This insight is temporarily unavailable. Please check back later."
  return (
    <div className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-5" role="status">
      <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div className="flex flex-col gap-0.5">
        <p className="text-sm font-medium">Not available yet</p>
        <p className="text-xs text-muted-foreground">{message}</p>
      </div>
    </div>
  )
}
