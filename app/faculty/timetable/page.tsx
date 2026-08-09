import { requireRole } from "@/lib/session"
import { getFacultyTimetable } from "@/lib/faculty-api"
import { ErrorState } from "@/components/shared/state/error-state"
import { TimetableView } from "@/components/faculty/timetable/timetable-view"

export default async function TimetablePage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Faculty")

  const searchParams = await props.searchParams
  const semester =
    typeof searchParams.semester === "string" ? parseInt(searchParams.semester) : undefined
  const academic_year =
    typeof searchParams.academic_year === "string" ? searchParams.academic_year : undefined

  const result = await getFacultyTimetable({ semester, academic_year })
  if (!result.ok) {
    return <ErrorState title="Failed to load timetable" description={result.error.message} />
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <TimetableView data={result.data} />
    </div>
  )
}
