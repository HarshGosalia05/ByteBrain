import Link from "next/link"
import { ArrowLeft } from "lucide-react"

import { requireRole } from "@/lib/session"
import {
  getFacultyStudentM1V2,
  getFacultyStudentM2V2,
  getFacultyStudentM3V2,
  getFacultyStudentMlInsights,
  getFacultyStudentProfile,
  type BffResult,
} from "@/lib/faculty-api"
import { PageHeader } from "@/components/shared/layout/page-header"
import { ErrorState } from "@/components/shared/state/error-state"
import { FacultyMlInsightsGrid } from "@/components/faculty/ml-insights/faculty-ml-insights-grid"

export default async function FacultyStudentMlInsightsPage(props: {
  params: Promise<{ studentId: string }>
}) {
  await requireRole("Faculty")

  const { studentId } = await props.params

  const [profileResult, insightsResult, m1v2Result, m2v2Result, m3v2Result] =
    await Promise.allSettled([
      getFacultyStudentProfile(studentId),
      getFacultyStudentMlInsights(studentId),
      getFacultyStudentM1V2(studentId),
      getFacultyStudentM2V2(studentId),
      getFacultyStudentM3V2(studentId),
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

  // A 404 on the M1/M2/M3 V2 routes is the deliberate NO_DATA boundary (e.g. the
  // student has no upcoming regular academic semester), not a real failure.
  const isNoData = (r: PromiseSettledResult<BffResult<unknown>>) =>
    r.status === "fulfilled" && !r.value.ok && r.value.error.status === 404

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
      <FacultyMlInsightsGrid
        data={insights.data}
        m1v2={m1v2Result.status === "fulfilled" && m1v2Result.value.ok ? m1v2Result.value.data : null}
        m1v2NoData={isNoData(m1v2Result)}
        m2v2={m2v2Result.status === "fulfilled" && m2v2Result.value.ok ? m2v2Result.value.data : null}
        m2v2NoData={isNoData(m2v2Result)}
        m3v2={m3v2Result.status === "fulfilled" && m3v2Result.value.ok ? m3v2Result.value.data : null}
        m3v2NoData={isNoData(m3v2Result)}
      />
    </div>
  )
}
