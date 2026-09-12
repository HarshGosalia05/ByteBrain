"use client"

import { SubjectsView } from "./subjects-view"
import type { FacultySubjectsResponse } from "@/lib/faculty-api"

export function SubjectsTabsView({
  allData,
}: {
  allData: FacultySubjectsResponse
}) {
  return <SubjectsView data={allData} />
}
