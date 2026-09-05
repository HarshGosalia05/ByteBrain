import {
  CalendarCheck,
  Gauge,
  GraduationCap,
  ListChecks,
  TriangleAlert,
  User,
} from "lucide-react"

import { requireRole } from "@/lib/session"
import {
  getAcademicSummary,
  getStudentPerformance,
  getStudentProfile,
  getGoals,
} from "@/lib/student-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { AvatarInitials } from "@/components/shared/data/avatar-initials"
import { StatCard } from "@/components/shared/data/stat-card"
import { ErrorState } from "@/components/shared/state/error-state"
import { EmptyState } from "@/components/shared/state/empty-state"
import { TrendChart } from "@/components/shared/charts/trend-chart"
import { Badge } from "@/components/ui/badge"
import { GoalsCard } from "@/components/student/goals/goals-card"

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-border/60 py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium tabular-nums">{value}</dd>
    </div>
  )
}

export default async function ProfilePage() {
  await requireRole("Student")

  const [profileResult, summaryResult, performanceResult, goalsResult] = await Promise.all([
    getStudentProfile(),
    getAcademicSummary(),
    getStudentPerformance(),
    getGoals(),
  ])

  if (!profileResult.ok) {
    return <ErrorState title="Profile unavailable" description={profileResult.error.message} />
  }

  const profile = profileResult.data
  const summaries = summaryResult.ok ? summaryResult.data.summaries : []
  const performance = performanceResult.ok ? performanceResult.data.performance : []

  const fetchedAt = [profileResult, summaryResult, performanceResult]
    .filter((r) => r.ok)
    .map((r) => r.fetchedAt)
    .sort()
    .pop()

  const completedSummaries = summaries.filter(
    (item) =>
      item.semester_percentage !== null &&
      item.semester_percentage > 0 &&
      item.sgpa > 0,
  )

  const latestSummary =
    completedSummaries.length > 0
      ? completedSummaries.reduce((max, item) => (item.semester > max.semester ? item : max))
      : null
  const totalCredits = completedSummaries.reduce((sum, item) => sum + item.total_credits_earned, 0)
  const averageAttendance =
    completedSummaries.length > 0
      ? completedSummaries.reduce((sum, item) => sum + item.attendance_percentage, 0) /
        completedSummaries.length
      : null
  const totalBacklogs = completedSummaries.reduce((sum, item) => sum + item.active_backlogs, 0)

  const fullName = `${profile.first_name} ${profile.last_name}`.trim()

  return (
    <div className="mx-auto flex max-w-full flex-col gap-6 lg:max-w-[95%]">
      <PageHeader
        title="Profile"
        description="Your student profile, academic statistics and summary."
        fetchedAt={fetchedAt}
      />

      <section className="flex flex-wrap items-center gap-4 rounded-xl bg-card p-5 ring-1 ring-foreground/10">
        <AvatarInitials firstName={profile.first_name} lastName={profile.last_name} size="lg" />
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-semibold tracking-tight">{fullName}</h2>
          <p className="text-sm text-muted-foreground">{profile.student_id}</p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <Badge variant="default">Semester {profile.current_semester}</Badge>
            {profile.department_name && (
              <Badge variant="outline">{profile.department_name}</Badge>
            )}
            <Badge variant="muted">Joined {profile.admission_year}</Badge>
          </div>
        </div>
      </section>

      <section
        className="grid grid-cols-2 gap-4 lg:grid-cols-4"
        aria-label="Academic statistics"
      >
        <StatCard
          label="Latest SGPA"
          value={latestSummary ? latestSummary.sgpa.toFixed(2) : "—"}
          icon={Gauge}
          hint={latestSummary ? `Semester ${latestSummary.semester}` : "No data yet"}
        />
        <StatCard
          label="Total credits"
          value={completedSummaries.length > 0 ? String(totalCredits) : "—"}
          icon={ListChecks}
          hint={`Across ${completedSummaries.length} semester${completedSummaries.length === 1 ? "" : "s"}`}
          tone="success"
        />
        <StatCard
          label="Avg attendance"
          value={averageAttendance !== null ? `${averageAttendance.toFixed(1)}%` : "—"}
          icon={CalendarCheck}
          hint="Semester average"
        />
        <StatCard
          label="Total backlogs"
          value={completedSummaries.length > 0 ? String(totalBacklogs) : "—"}
          icon={TriangleAlert}
          hint="Cumulative"
          tone={totalBacklogs > 0 ? "warning" : "success"}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2" aria-label="Personal and academic information">
        <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-2 text-sm font-semibold">Personal information</h3>
          <dl>
            <DetailRow label="Full name" value={fullName} />
            <DetailRow label="Student ID" value={profile.student_id} />
            <DetailRow label="Enrollment number" value={String(profile.enrollment_no)} />
            <DetailRow label="Admission year" value={String(profile.admission_year)} />
          </dl>
        </div>

        <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-2 text-sm font-semibold">Academic information</h3>
          <dl>
            <DetailRow label="Department" value={profile.department_name ?? "Not assigned"} />
            <DetailRow label="Current semester" value={`Semester ${profile.current_semester}`} />
            <DetailRow
              label="Latest SGPA"
              value={latestSummary ? latestSummary.sgpa.toFixed(2) : "—"}
            />
            <DetailRow
              label="Credits earned"
              value={completedSummaries.length > 0 ? String(totalCredits) : "—"}
            />
            <DetailRow
              label="Average attendance"
              value={averageAttendance !== null ? `${averageAttendance.toFixed(1)}%` : "—"}
            />
          </dl>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2" aria-label="Academic summary">
        <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
          <h3 className="mb-1 text-sm font-semibold">SGPA by semester</h3>          <p className="mb-4 text-xs text-muted-foreground">Grade point average per semester</p>
          {completedSummaries.length === 0 ? (
            <EmptyState
              icon={GraduationCap}
              title="No semester summaries yet"
              description="Your SGPA history will appear here once records are available."
            />
          ) : (
            <TrendChart
              data={completedSummaries.map((item) => ({
                semester: `Sem ${item.semester}`,
                sgpa: item.sgpa,
              }))}
              xKey="semester"
              series={[{ key: "sgpa", label: "SGPA", color: "var(--chart-1)" }]}
              yDomain={[0, 10]}
            />
          )}
        </div>

        <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
          <h3 className="mb-1 text-sm font-semibold">Attendance summary</h3>
          <p className="mb-4 text-xs text-muted-foreground">
            {performance.length > 0
              ? "Semester averages and subject-level attendance"
              : "Semester average attendance"}
          </p>
          {completedSummaries.length === 0 ? (
            <EmptyState
              icon={CalendarCheck}
              title="No attendance records yet"
              description="Your attendance summary will appear here once records are available."
            />
          ) : (
            <TrendChart
              data={completedSummaries.map((item) => ({
                semester: `Sem ${item.semester}`,
                attendance: item.attendance_percentage,
              }))}
              xKey="semester"
              series={[{ key: "attendance", label: "Attendance %", color: "var(--chart-2)" }]}
              yDomain={[0, 100]}
              yTickSuffix="%"
            />
          )}
        </div>
      </section>

      {performance.length > 0 && (
        <section className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-2 text-sm font-semibold">Subject performance</h3>
          <p className="mb-3 text-xs text-muted-foreground">
            Marks, grades and attendance across all recorded semesters.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Semester
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Subject
                  </th>
                  <th scope="col" className="py-2 pr-4 text-right font-medium">
                    Total
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Grade
                  </th>
                  <th scope="col" className="py-2 text-right font-medium">
                    Attendance
                  </th>
                </tr>
              </thead>
              <tbody>
                {performance.map((subject) => (
                  <tr
                    key={`${subject.semester}-${subject.subject_code}`}
                    className="border-b transition-colors last:border-0 hover:bg-muted/40"
                  >
                    <td className="py-2 pr-4 text-muted-foreground whitespace-nowrap">
                      Sem {subject.semester}
                    </td>
                    <td className="py-2 pr-4 font-medium whitespace-nowrap">
                      {subject.subject_name}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {subject.total_marks !== null ? subject.total_marks.toFixed(1) : "—"}
                    </td>
                    <td className="py-2 pr-4 whitespace-nowrap">
                      {subject.grade ?? "—"}
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      {subject.attendance_percentage !== null
                        ? `${subject.attendance_percentage.toFixed(1)}%`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {goalsResult.ok && (
        <GoalsCard
          initial={{
            student_id: profile.student_id,
            goals: goalsResult.data.goals,
          }}
        />
      )}

      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <User className="size-4" />
        Profile editing is not available yet. Settings for account preferences will arrive in a
        future phase.
      </p>
    </div>
  )
}
