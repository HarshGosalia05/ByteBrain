import { NextResponse } from "next/server"
import { clearFacultyNotification } from "@/lib/faculty-api"

export async function DELETE(
  _request: Request,
  props: { params: Promise<{ messageId: string }> },
) {
  const { messageId } = await props.params
  const result = await clearFacultyNotification(messageId)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
