import { NextResponse } from "next/server"

import { getMarksChangeLog } from "@/lib/faculty-api"

export async function GET(
  request: Request,
  props: { params: Promise<{ subjectId: string }> },
) {
  const { subjectId } = await props.params
  const url = new URL(request.url)
  const params = {
    semester: url.searchParams.get("semester")
      ? Number(url.searchParams.get("semester"))
      : undefined,
    academic_year: url.searchParams.get("academic_year") ?? undefined,
    page: url.searchParams.get("page") ? Number(url.searchParams.get("page")) : undefined,
    page_size: url.searchParams.get("page_size")
      ? Number(url.searchParams.get("page_size"))
      : undefined,
  }
  const result = await getMarksChangeLog(subjectId, params)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
