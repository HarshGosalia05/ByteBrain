"use server"

import {
  getFacultyPerformanceDistributions,
  getFacultyPerformanceInsights,
  getFacultyPerformanceLearningGaps,
  getFacultyPerformanceStudents,
  getFacultyPerformanceSubjectBreakdown,
  getFacultyPerformanceSummary,
  getFacultyPerformanceTrends,
  getFacultyPerformanceExport,
  type BffResult,
  type PerformanceExportParams,
  type PerformanceStudentsParams,
  type PerformanceSummary,
  type PerformanceSummaryParams,
} from "@/lib/faculty-api"

export async function refreshPerformanceSummaryAction(
  params: PerformanceSummaryParams,
): Promise<BffResult<PerformanceSummary>> {
  return getFacultyPerformanceSummary(params, { bypassCache: true })
}

export async function refreshPerformanceDataAction(
  summaryParams: PerformanceSummaryParams,
  studentsParams?: PerformanceStudentsParams,
): Promise<void> {
  await Promise.allSettled([
    getFacultyPerformanceSummary(summaryParams, { bypassCache: true }),
    getFacultyPerformanceDistributions(summaryParams, { bypassCache: true }),
    getFacultyPerformanceSubjectBreakdown(summaryParams, { bypassCache: true }),
    getFacultyPerformanceTrends(summaryParams, { bypassCache: true }),
    getFacultyPerformanceLearningGaps(summaryParams, { bypassCache: true }),
    getFacultyPerformanceInsights(summaryParams, { bypassCache: true }),
    getFacultyPerformanceStudents(studentsParams ?? {}, { bypassCache: true }),
  ])
}

export async function exportPerformanceCsvAction(
  params: PerformanceExportParams,
): Promise<BffResult<{ data: string }>> {
  const res = await getFacultyPerformanceExport(params)
  if (!res.ok) {
    return { ok: false, error: res.error }
  }
  return { ok: true, data: { data: res.data }, fetchedAt: res.fetchedAt }
}
