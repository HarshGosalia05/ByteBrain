import { NextResponse } from "next/server"
import { markNotificationRead } from "@/lib/student-api"

export async function PATCH(
  _request: Request,
  { params }: { params: Promise<{ messageId: string }> },
) {
  const { messageId } = await params
  const result = await markNotificationRead(messageId)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
