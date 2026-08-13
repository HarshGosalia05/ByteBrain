import Link from "next/link"
import { ArrowLeft } from "lucide-react"

import { requireRole } from "@/lib/session"
import { getFacultyStudentMlInsights, getFacultyStudentProfile } from "@/lib/faculty-api"
import { PageHeader } from "@/components/shared/layout/page-header"
import { ErrorState } from "@/components/shared/state/error-state"
import { FacultyMlInsightsGrid } from "@/components/faculty/ml-insights/faculty-ml-insights-grid"

export default async function FacultyStudentMlInsightsPage(props: {
  params: Promise<{ studentId: string }>
}) {
  await requireRole("Faculty")

  const { studentId } = await props.params

  const [profileResult, insightsResult] = await Promise.allSettled([
    getFacultyStudentProfile(studentId),
    getFacultyStudentMlInsights(studentId),
  ])

  const student =
    profileResult.status === "fulfilled" && profileResult.value.ok
      ? profileResult.value.data.student
      : null

  if (insightsResult.status === "rejected") {
    return (
      <ErrorState
        title="Failed to load insights"
        description="Something went wrong while loading this student's ML insights."
      />
    )
  }
  const insights = insightsResult.value
  if (!insights.ok) {
    return <ErrorState title="Insights unavailable" description={insights.error.message} />
  }

  const title = student ? `${student.first_name} ${student.last_name}` : `Student ${studentId}`
  const description = student
    ? `${student.enrollment_no} • ${student.department_name ?? "—"} • Semester ${student.current_semester ?? "—"}`
    : "ML predictions with grounded explanations"

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/faculty/students"
        className="flex w-fit items-center gap-1.5 text-sm font-medium text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back to students
      </Link>
      <PageHeader
        title={title}
        description={`${description} — predictions with the reasoning behind them and grounded next steps.`}
        fetchedAt={insights.ok ? insights.fetchedAt : null}
      />
      <FacultyMlInsightsGrid data={insights.data} />
    </div>
  )
}
