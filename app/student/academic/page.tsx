import { GraduationCap } from "lucide-react"

import { requireRole } from "@/lib/session"
import { getAcademicSummary } from "@/lib/student-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { EmptyState } from "@/components/shared/state/empty-state"
import { ErrorState } from "@/components/shared/state/error-state"
import { Badge } from "@/components/ui/badge"
import { SemesterSelect } from "@/components/student/semester-select"
import { SemesterChart } from "@/components/student/academic/semester-chart"

export default async function AcademicPage({
  searchParams,
}: {
  searchParams: Promise<{ semester?: string }>
}) {
  await requireRole("Student")

  const [{ semester: semesterParam }, result] = await Promise.all([
    searchParams,
    getAcademicSummary(),
  ])

  if (!result.ok) {
    return <ErrorState title="Academic history unavailable" description={result.error.message} />
  }

  const summaries = result.data.summaries
  const semesters = summaries.map((item) => item.semester)
  const selected = semesterParam ? Number(semesterParam) : null
  const visible =
    selected === null
      ? summaries
      : summaries.filter((item) => item.semester === selected)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Academic"
        description="Semester-by-semester academic history."
        fetchedAt={result.fetchedAt}
      />

      {summaries.length === 0 ? (
        <EmptyState
          icon={GraduationCap}
          title="No semester summaries yet"
          description="Your semester history will appear here once records are available."
        />
      ) : (
        <>
          <SemesterSelect semesters={semesters} current={Math.max(...semesters)} />

          <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
            <h2 className="mb-4 text-sm font-semibold">SGPA and attendance by semester</h2>
            <SemesterChart
              data={summaries.map((item) => ({
                semester: `Sem ${item.semester}`,
                sgpa: item.sgpa,
                attendance: item.attendance_percentage,
              }))}
            />
          </section>

          <section className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
            <table className="w-full text-sm">
              <caption className="sr-only">Semester academic summary</caption>
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-3 pl-4 pr-4 font-medium">
                    Semester
                  </th>
                  <th scope="col" className="py-3 pr-4 text-right font-medium">
                    SGPA
                  </th>
                  <th scope="col" className="py-3 pr-4 text-right font-medium">
                    Attendance
                  </th>
                  <th scope="col" className="py-3 pr-4 text-right font-medium">
                    Credits earned
                  </th>
                  <th scope="col" className="py-3 pr-4 font-medium">
                    Backlogs
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((item) => (
                  <tr key={item.semester} className="border-b last:border-0">
                    <td className="py-3 pl-4 pr-4 font-medium">Semester {item.semester}</td>
                    <td className="py-3 pr-4 text-right">{item.sgpa.toFixed(2)}</td>
                    <td className="py-3 pr-4 text-right">
                      {item.attendance_percentage.toFixed(1)}%
                    </td>
                    <td className="py-3 pr-4 text-right">{item.total_credits_earned}</td>
                    <td className="py-3 pr-4">
                      {item.active_backlogs > 0 ? (
                        <Badge variant="destructive">{item.active_backlogs} backlog</Badge>
                      ) : (
                        <Badge variant="success">None</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  )
}
