import { NextResponse } from "next/server"
import { getStudentPerformance } from "@/lib/student-api"

export async function GET() {
  const result = await getStudentPerformance()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
