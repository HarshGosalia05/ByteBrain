import { NextResponse } from "next/server"
import { clearNotification } from "@/lib/student-api"

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ messageId: string }> },
) {
  const { messageId } = await params
  const result = await clearNotification(messageId)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
