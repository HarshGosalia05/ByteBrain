import { NextRequest, NextResponse } from "next/server"
import { getFacultyAttendanceHeatmap } from "@/lib/faculty-api"

export async function GET(request: NextRequest) {
  const sp = request.nextUrl.searchParams
  const semesterRaw = sp.get("semester")
  const semester = semesterRaw ? parseInt(semesterRaw, 10) || null : null
  const academic_year = sp.get("academic_year") || undefined
  const subject_id = sp.get("subject_id") || undefined
  const page = Math.max(1, parseInt(sp.get("page") ?? "1", 10) || 1)
  const page_size = Math.min(50, Math.max(10, parseInt(sp.get("page_size") ?? "20", 10) || 20))

  const result = await getFacultyAttendanceHeatmap(
    { semester, academic_year, subject_id, page, page_size },
    { bypassCache: true },
  )

  return NextResponse.json(result, {
    status: result.ok ? 200 : result.error.status,
  })
}
