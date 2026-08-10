import { NextResponse } from "next/server"
import { getUnreadNotificationCount } from "@/lib/student-api"

export async function GET() {
  const result = await getUnreadNotificationCount()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
