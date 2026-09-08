import { NextResponse } from "next/server"
import {
  clearAllNotifications,
  getNotifications,
  type NotificationTypeFilter,
} from "@/lib/student-api"

const VALID_TYPES: NotificationTypeFilter[] = [
  "ATTENDANCE_WARNING",
  "ELIGIBILITY_WARNING",
  "MARKS_PUBLISHED",
  "MARKS_UPDATED",
  "MARKS_CLEARED",
  "PERFORMANCE_CHANGE",
  "RISK_ALERT",
  "TIMETABLE_CHANGE",
  "SYSTEM",
  "ANNOUNCEMENT",
  "ACADEMIC_NOTICE",
  "HOLIDAY",
  "EVENT",
  "SYSTEM_NOTICE",
]

export async function GET(request: Request) {
  const url = new URL(request.url)
  const messageType = url.searchParams.get("message_type")
  if (
    messageType !== null &&
    !VALID_TYPES.includes(messageType as NotificationTypeFilter)
  ) {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 422, code: "invalid", message: "Unknown notification type." },
      },
      { status: 422 },
    )
  }
  const result = await getNotifications({
    messageType: (messageType as NotificationTypeFilter) ?? undefined,
    unreadOnly: url.searchParams.get("unread_only") === "true",
    page: url.searchParams.get("page")
      ? Number(url.searchParams.get("page"))
      : undefined,
    pageSize: url.searchParams.get("page_size")
      ? Number(url.searchParams.get("page_size"))
      : undefined,
  })
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}

export async function DELETE() {
  const result = await clearAllNotifications()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
