"use server"

import {
  getFacultyWorkloadBenchmark,
  getFacultyWorkloadCapacity,
  getFacultyWorkloadExport,
  getFacultyWorkloadForecast,
  getFacultyWorkloadGovernance,
  getFacultyWorkloadHealthScore,
  getFacultyWorkloadHighlights,
  getFacultyWorkloadMatrices,
  getFacultyWorkloadScatter,
  getFacultyWorkloadStudents,
  getFacultyWorkloadSubjectBreakdown,
  getFacultyWorkloadSummary,
  getFacultyWorkloadTimeline,
  getFacultyWorkloadTrends,
  type BffResult,
  type WorkloadExportParams,
  type WorkloadStudentsParams,
  type WorkloadSummary,
  type WorkloadSummaryParams,
} from "@/lib/faculty-api"

export async function refreshWorkloadSummaryAction(
  params: WorkloadSummaryParams,
): Promise<BffResult<WorkloadSummary>> {
  return getFacultyWorkloadSummary(params, { bypassCache: true })
}

export async function refreshWorkloadDataAction(
  summaryParams: WorkloadSummaryParams,
  studentsParams?: WorkloadStudentsParams,
): Promise<void> {
  await Promise.allSettled([
    getFacultyWorkloadSummary(summaryParams, { bypassCache: true }),
    getFacultyWorkloadSubjectBreakdown(summaryParams, { bypassCache: true }),
    getFacultyWorkloadTrends(summaryParams, { bypassCache: true }),
    getFacultyWorkloadCapacity(summaryParams, { bypassCache: true }),
    getFacultyWorkloadMatrices(summaryParams, { bypassCache: true }),
    getFacultyWorkloadScatter(summaryParams, { bypassCache: true }),
    getFacultyWorkloadBenchmark(summaryParams, { bypassCache: true }),
    getFacultyWorkloadForecast({ bypassCache: true }),
    getFacultyWorkloadGovernance(summaryParams, { bypassCache: true }),
    getFacultyWorkloadHealthScore(summaryParams, { bypassCache: true }),
    getFacultyWorkloadTimeline({ bypassCache: true }),
    getFacultyWorkloadHighlights(summaryParams, { bypassCache: true }),
    getFacultyWorkloadStudents(studentsParams ?? {}, { bypassCache: true }),
  ])
}

export async function exportWorkloadCsvAction(
  params: WorkloadExportParams,
): Promise<BffResult<{ data: string }>> {
  const res = await getFacultyWorkloadExport(params)
  if (!res.ok) {
    return { ok: false, error: res.error }
  }
  const body = res.data
  const lineBreak = body.includes("\r\n") ? "\r\n" : "\n"
  const lines = body.split(lineBreak).filter((line) => line.length > 0)
  if (lines.length <= 1) {
    return {
      ok: false,
      error: {
        status: 200,
        code: "empty",
        message: "No rows match the current filters. Adjust the scope and try again.",
      },
    }
  }
  return { ok: true, data: { data: body }, fetchedAt: res.fetchedAt }
}
