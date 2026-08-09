import { NextResponse } from "next/server"
import { getFacultyTimetable } from "@/lib/faculty-api"

export async function GET(request: Request) {
  const url = new URL(request.url)
  const result = await getFacultyTimetable({
    semester: url.searchParams.get("semester")
      ? Number(url.searchParams.get("semester"))
      : undefined,
    academic_year: url.searchParams.get("academic_year") ?? undefined,
  })
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
