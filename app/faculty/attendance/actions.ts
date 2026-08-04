"use server"

import {
  getFacultyAttendanceDistributions,
  getFacultyAttendanceExport,
  getFacultyAttendanceGovernance,
  getFacultyAttendanceHealthScore,
  getFacultyAttendanceHighlights,
  getFacultyAttendanceStudents,
  getFacultyAttendanceSubjectBreakdown,
  getFacultyAttendanceSummary,
  getFacultyAttendanceTrends,
  type AttendanceExportParams,
  type AttendanceStudentsParams,
  type AttendanceSummary,
  type AttendanceSummaryParams,
  type BffResult,
} from "@/lib/faculty-api"

export async function refreshAttendanceSummaryAction(
  params: AttendanceSummaryParams,
): Promise<BffResult<AttendanceSummary>> {
  return getFacultyAttendanceSummary(params, { bypassCache: true })
}

export async function refreshAttendanceDataAction(
  summaryParams: AttendanceSummaryParams,
  studentsParams?: AttendanceStudentsParams,
): Promise<void> {
  await Promise.allSettled([
    getFacultyAttendanceSummary(summaryParams, { bypassCache: true }),
    getFacultyAttendanceDistributions(summaryParams, { bypassCache: true }),
    getFacultyAttendanceSubjectBreakdown(summaryParams, { bypassCache: true }),
    getFacultyAttendanceTrends(summaryParams, { bypassCache: true }),
    getFacultyAttendanceGovernance(summaryParams, { bypassCache: true }),
    getFacultyAttendanceHealthScore(summaryParams, { bypassCache: true }),
    getFacultyAttendanceHighlights(summaryParams, { bypassCache: true }),
    getFacultyAttendanceStudents(studentsParams ?? {}, { bypassCache: true }),
  ])
}

export async function exportAttendanceCsvAction(
  params: AttendanceExportParams,
): Promise<BffResult<{ data: string }>> {
  const res = await getFacultyAttendanceExport(params)
  if (!res.ok) {
    return { ok: false, error: res.error }
  }
  return { ok: true, data: { data: res.data }, fetchedAt: res.fetchedAt }
}
