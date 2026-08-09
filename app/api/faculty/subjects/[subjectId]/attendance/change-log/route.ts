import { NextResponse } from "next/server"

import { getAttendanceChangeLog } from "@/lib/faculty-api"

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
  const lectureDate = url.searchParams.get("lecture_date") ?? undefined
  const slotNoParam = url.searchParams.get("slot_no")
  const slotNo =
    slotNoParam && slotNoParam.trim() !== "" && !Number.isNaN(Number(slotNoParam))
      ? Number(slotNoParam)
      : undefined
  const params = {
    semester,
    academic_year,
    lecture_date: lectureDate,
    slot_no: slotNo,
    page: url.searchParams.get("page") ? Number(url.searchParams.get("page")) : undefined,
    page_size: url.searchParams.get("page_size")
      ? Number(url.searchParams.get("page_size"))
      : undefined,
  }
  const result = await getAttendanceChangeLog(subjectId, params)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
