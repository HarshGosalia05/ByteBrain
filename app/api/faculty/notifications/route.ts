import { NextResponse } from "next/server"
import {
  clearAllFacultyNotifications,
  getFacultyNotifications,
  type FacultyNotificationTypeFilter,
} from "@/lib/faculty-api"

const VALID_TYPES: FacultyNotificationTypeFilter[] = [
  "STUDENT_ATTENDANCE_WARNING",
  "STUDENT_ELIGIBILITY_WARNING",
  "STUDENT_PERFORMANCE_CHANGE",
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
    !VALID_TYPES.includes(messageType as FacultyNotificationTypeFilter)
  ) {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 422, code: "invalid", message: "Unknown notification type." },
      },
      { status: 422 },
    )
  }
  const result = await getFacultyNotifications({
    messageType: (messageType as FacultyNotificationTypeFilter) ?? undefined,
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
  const result = await clearAllFacultyNotifications()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
