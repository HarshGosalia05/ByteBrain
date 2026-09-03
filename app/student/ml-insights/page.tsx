import { requireRole } from "@/lib/session"
import { getSessionUser } from "@/lib/student-session"
import { getStudentCareerGuidance, getStudentM1V2, getStudentM1V3, getStudentM2V2, getStudentM3V2, getStudentMlInsights } from "@/lib/student-api"
import { getStudentSemesterHistory } from "@/lib/analytics-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { ErrorState } from "@/components/shared/state/error-state"
import { MlInsightsGrid } from "@/components/student/ml-insights/ml-insights-grid"
import { SemesterTrendChart } from "@/components/student/ml-insights/semester-trend-chart"

export const dynamic = "force-dynamic"

export default async function MlInsightsPage() {
  await requireRole("Student")

  const user = await getSessionUser()
  const studentId = user?.student_id ?? null

  // Guidance and the validated V2/V3 predictions degrade independently: a failure
  // in any must not break the existing ML insights bundle.
  const [result, guidanceResult, m1v2Result, m1v3Result, m2v2Result, m3v2Result, semHistoryResult] =
    await Promise.allSettled([
      getStudentMlInsights(),
      getStudentCareerGuidance(),
      getStudentM1V2(),
      getStudentM1V3(),
      getStudentM2V2(),
      getStudentM3V2(),
      studentId ? getStudentSemesterHistory(studentId) : Promise.resolve(null),
    ])

  const insights =
    result.status === "fulfilled" && result.value.ok ? result.value : null

  // M1 V2 now returns 200 with readiness_status="NO_DATA" for honest
  // unavailable-data states. We detect this by checking the data itself.
  const m1v2Data =
    m1v2Result.status === "fulfilled" && m1v2Result.value.ok
      ? m1v2Result.value.data
      : null
  const m1v2NoData =
    m1v2Data !== null &&
    m1v2Data.readiness_status === "NO_DATA" &&
    m1v2Data.subjects?.length === 0
  const m1v2Reason =
    m1v2NoData ? (m1v2Data?.reason ?? null) : null

  // M1 V3 (synthetic-trained model using real production data)
  const m1v3Data =
    m1v3Result.status === "fulfilled" && m1v3Result.value.ok
      ? m1v3Result.value.data
      : null
  const m1v3NoData =
    m1v3Data !== null &&
    m1v3Data.readiness_status === "NO_DATA" &&
    m1v3Data.subjects?.length === 0
  const m1v3Reason =
    m1v3NoData ? (m1v3Data?.reason ?? null) : null

  const m2v2Data =
    m2v2Result.status === "fulfilled" && m2v2Result.value.ok
      ? m2v2Result.value.data
      : null

  const semesterHistory =
    semHistoryResult.status === "fulfilled" && semHistoryResult.value?.ok
      ? semHistoryResult.value.data.semesters
      : []

  const predictedNextSemester =
    m2v2Data && m2v2Data.readiness_status === "READY"
      ? {
          sgpa: m2v2Data.predicted_next_semester_sgpa,
          percentage: m2v2Data.predicted_next_semester_percentage,
          semester_no: m2v2Data.prediction_takes_effect_semester,
        }
      : null

  const m1Prediction =
    m1v3Data && m1v3Data.subjects.length > 0
      ? m1v3Data
      : m1v2Data && m1v2Data.subjects.length > 0
        ? m1v2Data
        : null

  const currentSemester =
    m1Prediction && m1Prediction.subjects.length > 0
      ? {
          semester_no: m1Prediction.current_semester,
          predictedMarks: m1Prediction.subjects.map((s) => s.predicted_end_sem_marks),
        }
      : null

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="ML Insights"
        description="Personal predictions for your subjects, next semester and career readiness, with the reasoning behind each result."
        fetchedAt={insights && insights.ok ? insights.fetchedAt : null}
      />
      <SemesterTrendChart
        history={semesterHistory}
        predictedNextSemester={predictedNextSemester}
        currentSemester={currentSemester}
      />
      {!insights ? (
        <ErrorState
          title="Insights unavailable"
          description={
            result.status === "fulfilled" && !result.value.ok
              ? result.value.error.message
              : "Something went wrong while loading your insights."
          }
        />
      ) : (
        <MlInsightsGrid
          data={insights.data}
          guidance={
            guidanceResult.status === "fulfilled" && guidanceResult.value.ok
              ? guidanceResult.value.data
              : null
          }
          m1v2={m1v2NoData ? null : m1v2Data}
          m1v2NoData={m1v2NoData}
          m1v2Reason={m1v2Reason}
          m1v3={m1v3NoData ? null : m1v3Data}
          m1v3NoData={m1v3NoData}
          m1v3Reason={m1v3Reason}
          m2v2={
            m2v2Result.status === "fulfilled" && m2v2Result.value.ok
              ? m2v2Result.value.data
              : null
          }
          m2v2Reason={
            m2v2Result.status === "fulfilled" && !m2v2Result.value.ok && m2v2Result.value.error.status === 404
              ? m2v2Result.value.error.message
              : null
          }
          m3v2={
            m3v2Result.status === "fulfilled" && m3v2Result.value.ok
              ? m3v2Result.value.data
              : null
          }
          m3v2Reason={
            m3v2Result.status === "fulfilled" && !m3v2Result.value.ok && m3v2Result.value.error.status === 404
              ? m3v2Result.value.error.message
              : null
          }
        />
      )}
    </div>
  )
}
