import { NextResponse } from "next/server"
import { markAllNotificationsRead } from "@/lib/student-api"

export async function POST() {
  const result = await markAllNotificationsRead()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
