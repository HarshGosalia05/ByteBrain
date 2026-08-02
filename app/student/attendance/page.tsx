import { CalendarCheck } from "lucide-react"

import { requireRole } from "@/lib/session"
import { getAttendanceData } from "@/lib/student-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { EmptyState } from "@/components/shared/state/empty-state"
import { ErrorState } from "@/components/shared/state/error-state"
import { TrendChart } from "@/components/shared/charts/trend-chart"
import { Badge } from "@/components/ui/badge"
import { SemesterSelect } from "@/components/student/semester-select"

export default async function AttendancePage({
  searchParams,
}: {
  searchParams: Promise<{ semester?: string }>
}) {
  await requireRole("Student")

  const [{ semester: semesterParam }, result] = await Promise.all([
    searchParams,
    getAttendanceData(),
  ])

  if (!result.ok) {
    return <ErrorState title="Attendance data unavailable" description={result.error.message} />
  }

  const { summaries, performance } = result.data
  const summarySemesters = summaries.map((item) => item.semester)
  const performanceSemesters = [...new Set(performance.map((item) => item.semester))]
  const allSemesters = [...new Set([...summarySemesters, ...performanceSemesters])].sort(
    (a, b) => a - b,
  )

  const selected = semesterParam ? Number(semesterParam) : null
  const current = allSemesters.length > 0 ? Math.max(...allSemesters) : null
  const activeSemester = selected ?? current

  const visibleSubjects = performance.filter((item) => item.semester === activeSemester)
  const subjectsWithAttendance = visibleSubjects.filter(
    (item) => item.attendance_percentage !== null,
  )

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Attendance"
        description="Semester and subject attendance records."
        fetchedAt={result.fetchedAt}
      />

      {summaries.length === 0 && performance.length === 0 ? (
        <EmptyState
          icon={CalendarCheck}
          title="No attendance records yet"
          description="Your attendance records will appear here once they are available."
        />
      ) : (
        <>
          {allSemesters.length > 0 && (
            <SemesterSelect semesters={allSemesters} current={current ?? 1} />
          )}

          <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
            <h2 className="mb-4 text-sm font-semibold">Attendance by semester</h2>
            {summaries.length === 0 ? (
              <EmptyState
                icon={CalendarCheck}
                title="No semester attendance summaries"
                description="Your semester attendance trend will appear here once records are available."
              />
            ) : (
              <TrendChart
                data={summaries.map((item) => ({
                  semester: `Sem ${item.semester}`,
                  attendance: item.attendance_percentage,
                }))}
                xKey="semester"
                series={[{ key: "attendance", label: "Attendance %", color: "var(--chart-2)" }]}
                yDomain={[0, 100]}
                yTickSuffix="%"
              />
            )}
          </section>

          <section className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
            <div className="border-b px-4 py-3">
              <h2 className="text-sm font-semibold">
                Subject-wise attendance — Semester {activeSemester ?? "—"}
              </h2>
            </div>
            {subjectsWithAttendance.length === 0 ? (
              <div className="p-4">
                <EmptyState
                  icon={CalendarCheck}
                  title="No subject attendance recorded"
                  description="Subject attendance for this semester will appear here once records are available."
                />
              </div>
            ) : (
              <table className="w-full text-sm">
                <caption className="sr-only">Subject-wise attendance</caption>
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th scope="col" className="py-3 pl-4 pr-4 font-medium">
                      Code
                    </th>
                    <th scope="col" className="py-3 pr-4 font-medium">
                      Subject
                    </th>
                    <th scope="col" className="py-3 pr-4 text-right font-medium">
                      Attendance
                    </th>
                    <th scope="col" className="py-3 pr-4 font-medium">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {subjectsWithAttendance.map((subject) => {
                    const attendance = subject.attendance_percentage ?? 0
                    return (
                      <tr key={subject.subject_code} className="border-b transition-colors last:border-0 hover:bg-muted/40">
                        <td className="py-3 pl-4 pr-4 font-mono text-xs text-muted-foreground">
                          {subject.subject_code}
                        </td>
                        <td className="py-3 pr-4 font-medium">{subject.subject_name}</td>
                        <td className="py-3 pr-4 text-right tabular-nums">
                          {attendance.toFixed(1)}%
                        </td>
                        <td className="py-3 pr-4">
                          {attendance >= 75 ? (
                            <Badge variant="success">On track</Badge>
                          ) : (
                            <Badge variant="warning">Below 75%</Badge>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  )
}
