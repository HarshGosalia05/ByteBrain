import { Suspense } from "react"

import { requireRole } from "@/lib/session"
import { getSessionUser } from "@/lib/student-session"
import {
  getGoals,
  getStudentCareerGuidance,
  getStudentM1V3,
  getStudentM2TP,
  getStudentM3V2,
  getStudentMlInsights,
} from "@/lib/student-api"
import { getStudentSemesterHistory } from "@/lib/analytics-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { Skeleton } from "@/components/ui/skeleton"
import { ErrorState } from "@/components/shared/state/error-state"
import { MlInsightsGrid } from "@/components/student/ml-insights/ml-insights-grid"
import { SemesterTrendChart } from "@/components/student/ml-insights/semester-trend-chart"

export const dynamic = "force-dynamic"

function ChartFallback() {
  return (
    <div className="flex flex-col gap-3">
      <Skeleton className="h-5 w-64" />
      <Skeleton className="h-4 w-80 max-w-full" />
      <Skeleton className="h-[260px] w-full rounded-xl" />
    </div>
  )
}

function GridFallback() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="h-48 w-full rounded-xl" />
      <Skeleton className="h-48 w-full rounded-xl" />
      <Skeleton className="h-48 w-full rounded-xl" />
    </div>
  )
}

async function SemesterTrendSection() {
  const user = await getSessionUser()
  const studentId = user?.student_id ?? null

  const [m1v3Result, semHistoryResult, goalsResult] =
    await Promise.allSettled([
      getStudentM1V3(),
      studentId ? getStudentSemesterHistory(studentId) : Promise.resolve(null),
      getGoals(),
    ])

  const m1v3Data =
    m1v3Result.status === "fulfilled" && m1v3Result.value.ok
      ? m1v3Result.value.data
      : null

  const semesterHistory =
    semHistoryResult.status === "fulfilled" && semHistoryResult.value?.ok
      ? semHistoryResult.value.data.semesters
      : []

  const goals =
    goalsResult.status === "fulfilled" && goalsResult.value.ok
      ? goalsResult.value.data.goals
      : []

  const activeSgpaGoal = goals.find(
    (g) => g.goal_type === "target_sgpa" && g.status === "Active",
  )
  const activePercentageGoal = goals.find(
    (g) => g.goal_type === "target_percentage" && g.status === "Active",
  )

  // Pass the full Clean M1V3 subjects (credit + grade_band + predicted marks) so the
  // chart can compute credit-weighted SGPA via the university formula.
  const currentSemester =
    m1v3Data && m1v3Data.subjects.length > 0
      ? {
          semester_no: m1v3Data.current_semester,
          subjects: m1v3Data.subjects,
          predictedMarks: m1v3Data.subjects.map((s) => s.predicted_end_sem_marks),
        }
      : null

  return (
    <SemesterTrendChart
      history={semesterHistory}
      predictedNextSemester={null}
      currentSemester={currentSemester}
      targetSgpa={activeSgpaGoal?.target_value ?? null}
      targetPercentage={activePercentageGoal?.target_value ?? null}
    />
  )
}

async function MlInsightsSection() {
  const [result, guidanceResult, m1v3Result, m2tpResult, m3v2Result] =
    await Promise.allSettled([
      getStudentMlInsights(),
      getStudentCareerGuidance(),
      getStudentM1V3(),
      getStudentM2TP(),
      getStudentM3V2(),
    ])

  const insights =
    result.status === "fulfilled" && result.value.ok ? result.value : null

  const m1v3Data =
    m1v3Result.status === "fulfilled" && m1v3Result.value.ok
      ? m1v3Result.value.data
      : null
  const m1v3NoData =
    m1v3Data !== null &&
    m1v3Data.readiness_status === "NO_DATA" &&
    m1v3Data.subjects?.length === 0
  const m1v3Reason = m1v3NoData ? (m1v3Data?.reason ?? null) : null

  const m2tpData =
    m2tpResult.status === "fulfilled" && m2tpResult.value.ok
      ? m2tpResult.value.data
      : null
  const m2tpReason =
    m2tpResult.status === "fulfilled" && !m2tpResult.value.ok
      ? m2tpResult.value.error.message
      : (m2tpData?.reason ?? null)

  if (!insights) {
    return (
      <ErrorState
        title="Insights unavailable"
        description={
          result.status === "fulfilled" && !result.value.ok
            ? result.value.error.message
            : "Something went wrong while loading your insights."
        }
      />
    )
  }

  return (
    <MlInsightsGrid
      data={insights.data}
      guidance={
        guidanceResult.status === "fulfilled" && guidanceResult.value.ok
          ? guidanceResult.value.data
          : null
      }
      m1v3={m1v3NoData ? null : m1v3Data}
      m1v3NoData={m1v3NoData}
      m1v3Reason={m1v3Reason}
      m2tp={m2tpData}
      m2tpReason={m2tpReason}
      m3v2={
        m3v2Result.status === "fulfilled" && m3v2Result.value.ok
          ? m3v2Result.value.data
          : null
      }
      m3v2Reason={
        m3v2Result.status === "fulfilled" &&
        !m3v2Result.value.ok &&
        m3v2Result.value.error.status === 404
          ? m3v2Result.value.error.message
          : null
      }
    />
  )
}

export default async function MlInsightsPage() {
  await requireRole("Student")

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="ML Insights"
        description="Personal predictions for your subjects, next semester and career readiness, with the reasoning behind each result."
        fetchedAt={null}
      />
      <Suspense fallback={<ChartFallback />}>
        <SemesterTrendSection />
      </Suspense>
      <Suspense fallback={<GridFallback />}>
        <MlInsightsSection />
      </Suspense>
    </div>
  )
}
