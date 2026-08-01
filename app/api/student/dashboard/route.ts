import { NextResponse } from "next/server"
import { getDashboardData } from "@/lib/student-api"

export async function GET() {
  const result = await getDashboardData()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
