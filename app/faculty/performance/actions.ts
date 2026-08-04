"use server"

import {
  getFacultyPerformanceSummary,
  type BffResult,
  type PerformanceSummary,
  type PerformanceSummaryParams,
} from "@/lib/faculty-api"

export async function refreshPerformanceSummaryAction(
  params: PerformanceSummaryParams,
): Promise<BffResult<PerformanceSummary>> {
  return getFacultyPerformanceSummary(params, { bypassCache: true })
}
