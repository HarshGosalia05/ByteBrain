import { NextResponse } from "next/server"
import { getFacultySubjects } from "@/lib/faculty-api"

export async function GET(request: Request) {
  const url = new URL(request.url)
  const query = {
    semester: url.searchParams.get("semester") ?? undefined,
    academic_year: url.searchParams.get("academic_year") ?? undefined,
    search: url.searchParams.get("search") ?? undefined,
    page: url.searchParams.get("page") ? Number(url.searchParams.get("page")) : undefined,
    page_size: url.searchParams.get("page_size")
      ? Number(url.searchParams.get("page_size"))
      : undefined,
    sort: url.searchParams.get("sort") ?? undefined,
    order: url.searchParams.get("order") as "asc" | "desc" | undefined,
  }
  const result = await getFacultySubjects(query)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
