"use server"

import { getFacultyStudentOverview, type FacultyStudentOverview, type BffResult } from "@/lib/faculty-api"

export async function fetchStudentOverviewAction(
  studentId: string
): Promise<BffResult<FacultyStudentOverview>> {
  return getFacultyStudentOverview(studentId)
}
