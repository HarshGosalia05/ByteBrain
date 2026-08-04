import { requireRole } from "@/lib/session"
import { getFacultySubjectDetail, getFacultySubjectHistory } from "@/lib/faculty-api"
import { ErrorState } from "@/components/shared/state/error-state"
import { SubjectDetail } from "@/components/faculty/subjects/subject-detail"

export default async function SubjectDetailPage(props: {
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

  const [detailResult, historyResult] = await Promise.allSettled([
    getFacultySubjectDetail(id, { semester, academic_year }),
    getFacultySubjectHistory(id),
  ])

  if (detailResult.status === "rejected") {
    return (
      <ErrorState title="Failed to load subject" description="Something went wrong while loading this subject." />
    )
  }
  if (!detailResult.value.ok) {
    return <ErrorState title="Failed to load subject" description={detailResult.value.error.message} />
  }

  let history = null
  let historyError: string | null = null
  if (historyResult.status === "fulfilled") {
    if (historyResult.value.ok) {
      history = historyResult.value.data
    } else {
      historyError = historyResult.value.error.message
    }
  } else {
    historyError = "Something went wrong while loading the history."
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <SubjectDetail detail={detailResult.value.data} history={history} historyError={historyError} />
    </div>
  )
}
