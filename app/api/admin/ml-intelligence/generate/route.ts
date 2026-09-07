import { NextResponse } from "next/server"
import { startMLGeneration } from "@/lib/admin-api"

export async function POST(request: Request) {
  const reqBody = await request.json().catch(() => null)
  const models: string[] = Array.isArray(reqBody?.models)
    ? reqBody.models.filter((m: unknown) => typeof m === "string")
    : []
  const force = Boolean(reqBody?.force)

  const url = new URL(request.url)
  const dept = url.searchParams.get("department_code")
  const sem = url.searchParams.get("semester")
  const filters = {
    department_code: dept ? parseInt(dept, 10) || null : null,
    semester: sem ? parseInt(sem, 10) || null : null,
    batch: url.searchParams.get("batch"),
    academic_year: url.searchParams.get("academic_year"),
  }

  const result = await startMLGeneration(filters, models, force)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}