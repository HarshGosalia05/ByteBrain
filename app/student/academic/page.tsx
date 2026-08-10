import { AlertTriangle, BookOpen, CalendarDays, GraduationCap, Percent, TrendingUp } from "lucide-react"

import { requireRole } from "@/lib/session"
import {
  getAcademicSummary,
  getStudentAnalytics,
  getStudentPerformance,
} from "@/lib/student-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { EmptyState } from "@/components/shared/state/empty-state"
import { ErrorState } from "@/components/shared/state/error-state"
import { FreshnessBadge } from "@/components/shared/data/freshness-badge"
import { StatCard } from "@/components/shared/data/stat-card"
import { Badge } from "@/components/ui/badge"
import { SemesterSelect } from "@/components/student/semester-select"
import { SemesterChart } from "@/components/student/academic/semester-chart"
import { SubjectTable } from "@/components/student/subjects/subject-table"
import { PerformanceTrends } from "@/components/student/academic/performance-trends"
import { StrengthsWeaknesses } from "@/components/student/academic/strengths-weaknesses"
import { ClassBenchmark } from "@/components/student/academic/class-benchmark"
import { LearningGaps } from "@/components/student/academic/learning-gaps"
import { AttemptHistory } from "@/components/student/academic/attempt-history"
import { MarksSimulator } from "@/components/student/academic/marks-simulator"

function fmt(value: number | null, decimals: number, suffix = ""): string {
  return value === null ? "—" : `${value.toFixed(decimals)}${suffix}`
}

function ResultBadge({ result }: { result: string | null }) {
  if (result === null) return <Badge variant="muted">—</Badge>
  const normalized = result.toUpperCase()
  const variant =
    normalized === "PASS"
      ? "success"
      : normalized === "FAIL"
        ? "destructive"
        : "secondary"
  return <Badge variant={variant}>{result}</Badge>
}

export default async function AcademicPage({
  searchParams,
}: {
  searchParams: Promise<{ semester?: string }>
}) {
  await requireRole("Student")

  const [{ semester: semesterParam }, summaryResult, analyticsResult] = await Promise.all([
    searchParams,
    getAcademicSummary(),
    getStudentAnalytics(),
  ])

  if (!summaryResult.ok) {
    return (
      <ErrorState title="Academic history unavailable" description={summaryResult.error.message} />
    )
  }

  const { overview, summaries } = summaryResult.data
  const semesters = [...new Set(summaries.map((item) => item.semester))].sort(
    (a, b) => a - b,
  )
  const current = Math.max(...semesters)
  const selected = semesterParam ? Number(semesterParam) : null
  const activeSemester =
    selected !== null && semesters.includes(selected) ? selected : current

  const performanceResult = await getStudentPerformance(activeSemester)
  const performance = performanceResult.ok ? performanceResult.data.performance : []

  const simulatorSubjects = performance.map((item) => ({
    subject_code: item.subject_code,
    subject_name: item.subject_name,
    internal_marks: item.internal_marks,
    mid_sem_marks: item.mid_sem_marks,
    end_sem_marks: item.end_sem_marks,
  }))

  const chartData = summaries.map((item) => ({
    semester: `Sem ${item.semester}`,
    sgpa: item.sgpa,
    attendance: item.attendance_percentage,
    percentage: item.semester_percentage,
  }))

  const backlogTone =
    overview.total_backlogs !== null && overview.total_backlogs > 0
      ? ("destructive" as const)
      : ("success" as const)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Academic"
        description="Semester-by-semester academic history."
        fetchedAt={summaryResult.fetchedAt}
      />

      {summaries.length === 0 ? (
        <EmptyState
          icon={GraduationCap}
          title="No semester summaries yet"
          description="Your semester history will appear here once records are available."
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <StatCard
              label="Latest SGPA"
              value={fmt(overview.latest_sgpa, 2)}
              icon={TrendingUp}
              hint={overview.current_academic_year ?? "Not available"}
            />
            <StatCard
              label="Overall CGPA"
              value={fmt(overview.overall_cgpa, 2)}
              icon={GraduationCap}
              hint={
                overview.current_semester === null
                  ? "Not available"
                  : `Semester ${overview.current_semester}`
              }
            />
            <StatCard
              label="Overall Percentage"
              value={fmt(overview.overall_percentage, 2, "%")}
              icon={Percent}
            />
            <StatCard
              label="Credits earned"
              value={fmt(overview.total_credits_earned, 0)}
              icon={BookOpen}
              hint={`of ${fmt(overview.total_credits_registered, 0)} registered`}
            />
            <StatCard
              label="Backlogs"
              value={fmt(overview.total_backlogs, 0)}
              icon={AlertTriangle}
              hint={overview.academic_standing ?? "Not available"}
              tone={backlogTone}
            />
            <StatCard
              label="Current semester"
              value={
                overview.current_semester === null
                  ? "—"
                  : `Sem ${overview.current_semester}`
              }
              icon={CalendarDays}
              hint={overview.current_academic_year ?? "Not available"}
            />
          </div>

          <SemesterSelect semesters={semesters} current={current} />

          <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
            <h2 className="mb-4 text-sm font-semibold">SGPA, attendance and semester percentage by semester</h2>
            <SemesterChart data={chartData} />
          </section>

          <section className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
            <h2 className="px-4 pt-4 text-sm font-semibold">Semester history</h2>
            <table className="w-full min-w-[900px] text-sm">
              <caption className="sr-only">Semester academic summary</caption>
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-3 pl-4 pr-4 font-medium">
                    Semester
                  </th>
                  <th scope="col" className="py-3 pr-4 text-right font-medium">
                    Subjects
                  </th>
                  <th scope="col" className="py-3 pr-4 text-right font-medium">
                    Credits (reg / earned)
                  </th>
                  <th scope="col" className="py-3 pr-4 text-right font-medium">
                    Percentage
                  </th>
                  <th scope="col" className="py-3 pr-4 font-medium">
                    Grade
                  </th>
                  <th scope="col" className="py-3 pr-4 text-right font-medium">
                    SGPA
                  </th>
                  <th scope="col" className="py-3 pr-4 text-right font-medium">
                    Attendance
                  </th>
                  <th scope="col" className="py-3 pr-4 font-medium">
                    Result
                  </th>
                  <th scope="col" className="py-3 pr-4 font-medium">
                    Backlogs
                  </th>
                  <th scope="col" className="py-3 pr-4 font-medium">
                    Standing
                  </th>
                </tr>
              </thead>
              <tbody>
                {summaries.map((item) => (
                  <tr key={item.semester} className="border-b transition-colors last:border-0 hover:bg-muted/40">
                    <td className="py-3 pl-4 pr-4">
                      <span className="font-medium">Semester {item.semester}</span>
                      {item.academic_year && (
                        <span className="block text-xs text-muted-foreground">
                          {item.academic_year}
                        </span>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums">
                      {fmt(item.subjects_registered, 0)}
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums">
                      {fmt(item.credits_registered, 0)} / {item.total_credits_earned}
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums">
                      {fmt(item.semester_percentage, 2, "%")}
                    </td>
                    <td className="py-3 pr-4">
                      {item.semester_grade === null ? (
                        <Badge variant="muted">—</Badge>
                      ) : (
                        <Badge variant="secondary">{item.semester_grade}</Badge>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums">{item.sgpa.toFixed(2)}</td>
                    <td className="py-3 pr-4 text-right tabular-nums">
                      {item.attendance_percentage.toFixed(1)}%
                    </td>
                    <td className="py-3 pr-4">
                      <ResultBadge result={item.semester_result} />
                    </td>
                    <td className="py-3 pr-4">
                      {item.active_backlogs > 0 ? (
                        <Badge variant="destructive">{item.active_backlogs} backlog</Badge>
                      ) : (
                        <Badge variant="success">None</Badge>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      {item.academic_standing === null ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        item.academic_standing
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="rounded-xl bg-card ring-1 ring-foreground/10">
            <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-4">
              <h2 className="text-sm font-semibold">Subject marks — Semester {activeSemester}</h2>
              <FreshnessBadge fetchedAt={performanceResult.ok ? performanceResult.fetchedAt : null} />
            </div>
            {!performanceResult.ok ? (
              <div className="p-6">
                <p className="text-sm text-muted-foreground">{performanceResult.error.message}</p>
              </div>
            ) : performance.length === 0 ? (
              <EmptyState
                icon={BookOpen}
                title="No subject records for this semester"
                description="Select another semester or check back once records are available."
              />
            ) : (
              <SubjectTable rows={performance} />
            )}
          </section>

          <MarksSimulator subjects={simulatorSubjects} />

          {!analyticsResult.ok ? (
            <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
              <h2 className="text-sm font-semibold">Advanced insights</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {analyticsResult.error.message}
              </p>
            </section>
          ) : (
            <>
              <PerformanceTrends trends={analyticsResult.data.trends} />
              <StrengthsWeaknesses
                strengths={analyticsResult.data.strengths}
                needsAttention={analyticsResult.data.needs_attention}
              />
              <ClassBenchmark items={analyticsResult.data.class_benchmark} />
              <LearningGaps gaps={analyticsResult.data.learning_gaps} />
              <AttemptHistory items={analyticsResult.data.attempt_history} />
            </>
          )}
        </>
      )}
    </div>
  )
}