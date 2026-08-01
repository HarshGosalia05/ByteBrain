import { NextResponse } from "next/server"
import { getAcademicSummary } from "@/lib/student-api"

export async function GET() {
  const result = await getAcademicSummary()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
