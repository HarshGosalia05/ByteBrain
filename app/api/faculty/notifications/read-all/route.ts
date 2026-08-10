import { NextResponse } from "next/server"
import { markAllFacultyNotificationsRead } from "@/lib/faculty-api"

export async function POST() {
  const result = await markAllFacultyNotificationsRead()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
