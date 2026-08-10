import { requireRole } from "@/lib/session"
import { getDailyAssistant, getStudentTimetable } from "@/lib/student-api"
import { ErrorState } from "@/components/shared/state/error-state"
import { TimetableView } from "@/components/student/timetable/timetable-view"

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

export default async function TimetablePage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>
}) {
  await requireRole("Student")

  const [{ date: dateParam }] = await Promise.all([searchParams])
  const date = dateParam && DATE_RE.test(dateParam) ? dateParam : undefined

  const [timetableResult, dailyResult] = await Promise.all([
    getStudentTimetable(),
    getDailyAssistant(date),
  ])

  if (!dailyResult.ok) {
    return (
      <ErrorState
        title="Daily schedule unavailable"
        description={dailyResult.error.message}
      />
    )
  }

  return (
    <TimetableView
      daily={dailyResult.data}
      timetable={timetableResult.ok ? timetableResult.data : null}
      fetchedAt={dailyResult.fetchedAt}
    />
  )
}
