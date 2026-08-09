import { requireRole } from "@/lib/session"
import { getFacultySubjects, getFacultyTimetable, getFullTimetable } from "@/lib/faculty-api"
import { ErrorState } from "@/components/shared/state/error-state"
import { TimetableView } from "@/components/faculty/timetable/timetable-view"

export default async function TimetablePage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Faculty")

  const searchParams = await props.searchParams
  // Never forward an empty "semester=" from the URL: parseInt("") is NaN, and a
  // NaN semester reaches FastAPI as a query-string "semester=NaN", which fails
  // its Optional[int] coercion (HTTP 422). A missing term resolves to the
  // faculty's current teaching term on the backend.
  const rawSemester = typeof searchParams.semester === "string" ? searchParams.semester : undefined
  const semester =
    rawSemester && rawSemester.trim() !== "" && Number.isInteger(Number(rawSemester))
      ? Number(rawSemester)
      : undefined
  const academic_year =
    typeof searchParams.academic_year === "string" && searchParams.academic_year.trim() !== ""
      ? searchParams.academic_year
      : undefined

  const [timetableResult, subjectsResult, fullTimetableResult] = await Promise.all([
    getFacultyTimetable({ semester, academic_year }),
    getFacultySubjects({ page_size: 50 }),
    getFullTimetable({ semester, academic_year }),
  ])
  if (!timetableResult.ok) {
    return <ErrorState title="Failed to load timetable" description={timetableResult.error.message} />
  }

  const semesterOptions = subjectsResult.ok ? subjectsResult.data.filters.semesters : []

  return (
    <div className="flex flex-col gap-6 p-6">
      <TimetableView
        data={timetableResult.data}
        fullTimetable={fullTimetableResult.ok ? fullTimetableResult.data : null}
        semester={semester ?? null}
        semesterOptions={semesterOptions}
      />
    </div>
  )
}
