import { NextResponse } from "next/server"

import { saveLectureAttendance, type LectureAttendanceSaveRequest } from "@/lib/faculty-api"

export async function POST(
  request: Request,
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
