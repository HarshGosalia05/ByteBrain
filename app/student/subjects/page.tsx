import { BookOpen } from "lucide-react"

import { requireRole } from "@/lib/session"
import { getStudentPerformance } from "@/lib/student-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { EmptyState } from "@/components/shared/state/empty-state"
import { ErrorState } from "@/components/shared/state/error-state"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"
import { SemesterSelect } from "@/components/student/semester-select"
import { SubjectTable } from "@/components/student/subjects/subject-table"

export default async function SubjectsPage({
  searchParams,
}: {
  searchParams: Promise<{ semester?: string }>
}) {
  await requireRole("Student")

  const [{ semester: semesterParam }, result] = await Promise.all([
    searchParams,
    getStudentPerformance(),
  ])

  if (!result.ok) {
    return <ErrorState title="Subject data unavailable" description={result.error.message} />
  }

  const performance = result.data.performance
  const semesters = [...new Set(performance.map((item) => item.semester))].sort(
    (a, b) => a - b,
  )
  const selected = semesterParam ? Number(semesterParam) : null
  const current = semesters.length > 0 ? Math.max(...semesters) : null
  const activeSemester = selected ?? current

  const visible = performance.filter((item) => item.semester === activeSemester)
  const barData = visible.map((item) => ({
    subject: item.subject_name.length > 18 ? `${item.subject_name.slice(0, 18)}…` : item.subject_name,
    total: item.total_marks ?? 0,
  }))

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Subjects"
        description="Marks, grades and attendance for each subject."
        fetchedAt={result.fetchedAt}
      />

      {performance.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="No subject records yet"
          description="Your subject performance will appear here once records are available."
        />
      ) : (
        <>
          <SemesterSelect semesters={semesters} current={current ?? 1} />

          <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
            <h2 className="mb-4 text-sm font-semibold">
              Total marks by subject — Semester {activeSemester}
            </h2>
            {visible.length === 0 ? (
              <EmptyState
                icon={BookOpen}
                title="No subjects recorded for this semester"
                description="Select another semester or check back once records are available."
              />
            ) : (
              <SubjectBarChart
                data={barData}
                xKey="subject"
                dataKey="total"
                color="var(--chart-1)"
              />
            )}
          </section>

          <section className="rounded-xl bg-card ring-1 ring-foreground/10">
            {visible.length === 0 ? null : <SubjectTable rows={visible} />}
          </section>
        </>
      )}
    </div>
  )
}
