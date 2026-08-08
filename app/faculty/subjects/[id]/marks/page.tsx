import { requireRole } from "@/lib/session"
import { getSubjectMarks } from "@/lib/faculty-api"
import { ErrorState } from "@/components/shared/state/error-state"
import { MarksEntryView } from "@/components/faculty/subjects/marks-entry/marks-entry-view"

export default async function MarksEntryPage(props: {
  params: Promise<{ id: string }>
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Faculty")

  const { id } = await props.params
  const searchParams = await props.searchParams
  const semester =
    typeof searchParams.semester === "string" ? parseInt(searchParams.semester) : undefined
  const academic_year =
    typeof searchParams.academic_year === "string" ? searchParams.academic_year : undefined

  const result = await getSubjectMarks(id, { semester, academic_year })
  if (!result.ok) {
    return <ErrorState title="Failed to load marks" description={result.error.message} />
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <MarksEntryView
        subjectId={id}
        initialGrid={result.data}
        fetchedAt={result.fetchedAt}
        semester={semester}
        academicYear={academic_year}
      />
    </div>
  )
}
