import { requireRole } from "@/lib/session"
import { getFacultySubjects } from "@/lib/faculty-api"
import { ErrorState } from "@/components/shared/state/error-state"
import { SubjectsView } from "@/components/faculty/subjects/subjects-view"

export default async function SubjectsPage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Faculty")

  const searchParams = await props.searchParams
  const page = typeof searchParams.page === "string" ? parseInt(searchParams.page) || 1 : 1
  const search = typeof searchParams.search === "string" ? searchParams.search : undefined
  const semester =
    typeof searchParams.semester === "string" ? searchParams.semester : undefined
  const academic_year =
    typeof searchParams.academic_year === "string" ? searchParams.academic_year : undefined
  const sort = typeof searchParams.sort === "string" ? searchParams.sort : undefined
  const order =
    typeof searchParams.order === "string" ? (searchParams.order as "asc" | "desc") : undefined

  const res = await getFacultySubjects({ page, search, semester, academic_year, sort, order })
  if (!res.ok) {
    return <ErrorState title="Failed to load subjects" description={res.error.message} />
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Subjects</h1>
        <p className="text-muted-foreground mt-2">
          Subjects you teach, with enrollment, performance and attendance per subject.
        </p>
      </div>
      <SubjectsView data={res.data} />
    </div>
  )
}
