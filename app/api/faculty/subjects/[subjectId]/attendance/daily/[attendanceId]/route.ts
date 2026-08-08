import { NextResponse } from "next/server"

import { correctLectureAttendance } from "@/lib/faculty-api"

export async function PATCH(
  request: Request,
  props: { params: Promise<{ subjectId: string; attendanceId: string }> },
) {
  const { subjectId, attendanceId } = await props.params
  let body: { status?: "P" | "A" }
  try {
    body = (await request.json()) as typeof body
  } catch {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 400, code: "invalid", message: "Invalid request body." },
      },
      { status: 400 },
    )
  }
  if (body.status !== "P" && body.status !== "A") {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 400, code: "invalid", message: "status must be P or A." },
      },
      { status: 400 },
    )
  }
  const result = await correctLectureAttendance(subjectId, Number(attendanceId), body.status)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
