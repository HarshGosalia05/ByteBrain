import { requireRole } from "@/lib/session"
import { getFacultySubjects } from "@/lib/faculty-api"
import { ErrorState } from "@/components/shared/state/error-state"
import { AttendanceEntryView } from "@/components/faculty/attendance/entry/attendance-entry-view"

export default async function AttendanceEntryPage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Faculty")

  const searchParams = await props.searchParams
  const subjectId =
    typeof searchParams.subject_id === "string" ? searchParams.subject_id : undefined
  const semester =
    typeof searchParams.semester === "string" ? parseInt(searchParams.semester) : undefined
  const academic_year =
    typeof searchParams.academic_year === "string" ? searchParams.academic_year : undefined

  const result = await getFacultySubjects({ page_size: 50 })
  if (!result.ok) {
    return <ErrorState title="Failed to load subjects" description={result.error.message} />
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <AttendanceEntryView
        subjectOptions={result.data.cards}
        initialSubjectId={subjectId}
        initialSemester={semester}
        initialAcademicYear={academic_year}
      />
    </div>
  )
}
