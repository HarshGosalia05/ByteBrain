import { NextResponse } from "next/server"
import {
  getSubjectMarks,
  saveSubjectMarks,
  type MarksBatchSaveRequest,
} from "@/lib/faculty-api"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ subjectId: string }> },
) {
  const { subjectId } = await params
  const url = new URL(request.url)
  const query = {
    semester: url.searchParams.get("semester")
      ? Number(url.searchParams.get("semester"))
      : undefined,
    academic_year: url.searchParams.get("academic_year") ?? undefined,
    page: url.searchParams.get("page") ? Number(url.searchParams.get("page")) : undefined,
    page_size: url.searchParams.get("page_size")
      ? Number(url.searchParams.get("page_size"))
      : undefined,
    sort: url.searchParams.get("sort") ?? undefined,
    order: url.searchParams.get("order") as "asc" | "desc" | undefined,
  }
  const result = await getSubjectMarks(subjectId, query, {
    bypassCache: url.searchParams.get("refresh") === "1",
  })
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ subjectId: string }> },
) {
  const { subjectId } = await params
  let body: MarksBatchSaveRequest
  try {
    body = (await request.json()) as MarksBatchSaveRequest
  } catch {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 400, code: "invalid", message: "Invalid request body." },
      },
      { status: 400 },
    )
  }
  const result = await saveSubjectMarks(subjectId, body)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
