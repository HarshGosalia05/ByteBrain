import { NextResponse } from "next/server"
import { getAttendanceData } from "@/lib/student-api"

export async function GET() {
  const result = await getAttendanceData()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
