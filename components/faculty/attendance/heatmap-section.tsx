import { getFacultyAttendanceHeatmap } from "@/lib/faculty-api"
import type { AttendanceSummaryParams, AttendanceThresholds } from "@/lib/faculty-api"

import { HeatmapGridPagination } from "./heatmap-grid-pagination"

export async function HeatmapSection({
  filters,
  thresholds,
}: {
  filters: AttendanceSummaryParams
  thresholds: AttendanceThresholds
}) {
  const result = await getFacultyAttendanceHeatmap(
    { ...filters, page: 1, page_size: 20 },
    { bypassCache: true },
  )

  if (!result.ok) {
    return (
      <section id="attendance-heatmap" className="flex scroll-mt-6 flex-col gap-5">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Attendance heatmap</h2>
          <p className="text-sm text-destructive">{result.error.message}</p>
        </div>
      </section>
    )
  }

  return (
    <HeatmapGridPagination
      initialData={result.data}
      filters={filters}
      thresholds={thresholds}
    />
  )
}
