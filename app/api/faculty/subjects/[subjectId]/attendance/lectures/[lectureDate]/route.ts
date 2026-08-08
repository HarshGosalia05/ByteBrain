import { NextResponse } from "next/server"

import {
  getLectureAttendance,
  saveLectureAttendance,
  type LectureAttendanceSaveRequest,
} from "@/lib/faculty-api"

export async function GET(
  request: Request,
  props: { params: Promise<{ subjectId: string; lectureDate: string }> },
) {
  const { subjectId, lectureDate } = await props.params
  const url = new URL(request.url)
  const slot_no = url.searchParams.get("slot_no")
  if (!slot_no) {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 400, code: "invalid", message: "slot_no is required." },
      },
      { status: 400 },
    )
  }
  const result = await getLectureAttendance(
    subjectId,
    {
      lecture_date: lectureDate,
      slot_no: Number(slot_no),
      semester: url.searchParams.get("semester")
        ? Number(url.searchParams.get("semester"))
        : undefined,
      academic_year: url.searchParams.get("academic_year") ?? undefined,
    },
    { bypassCache: url.searchParams.get("refresh") === "1" },
  )
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}

export async function PATCH(
  request: Request,
  props: { params: Promise<{ subjectId: string; lectureDate: string }> },
) {
  const { subjectId, lectureDate } = await props.params
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
  body.lecture_date = lectureDate
  body.allow_correction = true
  const result = await saveLectureAttendance(subjectId, body)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
