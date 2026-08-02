import { NextResponse } from "next/server"
import { getFacultyDashboard } from "@/lib/faculty-api"

export async function GET() {
  const result = await getFacultyDashboard()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
