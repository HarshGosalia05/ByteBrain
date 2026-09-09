import { requireRole } from "@/lib/session"
import {
  getFacultySubjects,
  getFacultyCurrentSubjects,
  getFacultyPreviousBatch,
  getFacultyTeachingHistory,
} from "@/lib/faculty-api"
import { ErrorState } from "@/components/shared/state/error-state"
import { SubjectsTabsView } from "@/components/faculty/subjects/subjects-tabs-view"

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
  const batch =
    typeof searchParams.batch === "string" ? searchParams.batch : undefined
  const sort = typeof searchParams.sort === "string" ? searchParams.sort : undefined
  const order =
    typeof searchParams.order === "string" ? (searchParams.order as "asc" | "desc") : undefined
  const all_terms = searchParams.all_terms === "true"

  const [allResult, currentResult, previousResult, historyResult] = await Promise.allSettled([
    getFacultySubjects({ page, search, semester, academic_year, batch, sort, order, all_terms }),
    getFacultyCurrentSubjects(),
    getFacultyPreviousBatch(),
    getFacultyTeachingHistory(),
  ])

  if (allResult.status !== "fulfilled" || !allResult.value.ok) {
    const error = allResult.status === "fulfilled" ? allResult.value : allResult.reason
    return (
      <ErrorState
        title="Failed to load subjects"
        description={error?.error?.message ?? "Unable to load subjects right now."}
      />
    )
  }
  const allData = allResult.value.data

  const current =
    currentResult.status === "fulfilled" && currentResult.value.ok
      ? currentResult.value.data
      : null
  const previous =
    previousResult.status === "fulfilled" && previousResult.value.ok
      ? previousResult.value.data
      : null
  const history =
    historyResult.status === "fulfilled" && historyResult.value.ok
      ? historyResult.value.data
      : null

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Subjects</h1>
        <p className="text-muted-foreground mt-2">
          Current-semester subjects, previous-batch teaching history and your full teaching record.
        </p>
      </div>
      <SubjectsTabsView
        allData={allData}
        currentData={current}
        previousData={previous}
        historyData={history}
        initialTab={
          typeof searchParams.tab === "string"
            ? searchParams.tab
            : current
              ? "current"
              : "all"
        }
      />
    </div>
  )
}