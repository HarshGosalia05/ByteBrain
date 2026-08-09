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
  const semesterParam = url.searchParams.get("semester")
  const semester =
    semesterParam && semesterParam.trim() !== "" && !Number.isNaN(Number(semesterParam))
      ? Number(semesterParam)
      : undefined
  const academic_year = (url.searchParams.get("academic_year") ?? "").trim() || undefined
  const result = await getLectureAttendance(
    subjectId,
    {
      lecture_date: lectureDate,
      slot_no: Number(slot_no),
      semester,
      academic_year,
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
