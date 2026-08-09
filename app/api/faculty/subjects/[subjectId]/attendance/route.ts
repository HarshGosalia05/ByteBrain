import { NextResponse } from "next/server"

import {
  getAttendanceEntryMeta,
  saveLectureAttendance,
  type LectureAttendanceSaveRequest,
} from "@/lib/faculty-api"

export async function GET(
  request: Request,
  props: { params: Promise<{ subjectId: string }> },
) {
  const { subjectId } = await props.params
  const url = new URL(request.url)
  const semesterParam = url.searchParams.get("semester")
  const semester =
    semesterParam && semesterParam.trim() !== "" && !Number.isNaN(Number(semesterParam))
      ? Number(semesterParam)
      : undefined
  const academic_year = (url.searchParams.get("academic_year") ?? "").trim() || undefined
  const result = await getAttendanceEntryMeta(subjectId, { semester, academic_year }, {
    bypassCache: url.searchParams.get("refresh") === "1",
  })
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}

export async function POST(  request: Request,
  props: { params: Promise<{ subjectId: string }> },
) {
  const { subjectId } = await props.params
  let body: LectureAttendanceSaveRequest
  try {
    body = (await request.json()) as LectureAttendanceSaveRequest
  } catch {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 400, code: "invalid", message: "Invalid request body." },
      },
      { status: 400 },
    )
  }
  const result = await saveLectureAttendance(subjectId, body)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
