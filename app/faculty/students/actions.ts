"use server"

import { getFacultyStudentProfile, type FacultyStudentProfileView, type BffResult } from "@/lib/faculty-api"

export async function fetchStudentProfileAction(
  studentId: string
): Promise<BffResult<FacultyStudentProfileView>> {
  return getFacultyStudentProfile(studentId)
}
