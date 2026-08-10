import { NextResponse } from "next/server"
import { markFacultyNotificationRead } from "@/lib/faculty-api"

export async function PATCH(
  _request: Request,
  props: { params: Promise<{ messageId: string }> },
) {
  const { messageId } = await props.params
  const result = await markFacultyNotificationRead(messageId)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
