import { NextResponse } from "next/server"
import { getFacultyUnreadNotificationCount } from "@/lib/faculty-api"

export async function GET() {
  const result = await getFacultyUnreadNotificationCount()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
