import { NextResponse } from "next/server"
import { getStudentHealthData } from "@/lib/student-api"

export async function GET() {
  const result = await getStudentHealthData()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
