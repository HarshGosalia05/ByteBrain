import Link from "next/link"
import {
  ArrowRight,
  BookOpen,
  CalendarCheck,
  Gauge,
  GraduationCap,
  ListChecks,
  TriangleAlert,
} from "lucide-react"

import type { DashboardData } from "@/lib/student-api"

import { AvatarInitials } from "@/components/shared/data/avatar-initials"
import { FreshnessBadge } from "@/components/shared/data/freshness-badge"
import { GradeBadge } from "@/components/shared/data/grade-badge"
import { StatCard } from "@/components/shared/data/stat-card"
import { EmptyState } from "@/components/shared/state/empty-state"
import { TrendChart } from "@/components/shared/charts/trend-chart"

export function DashboardView({
  data,
  fetchedAt,
}: {
  data: DashboardData
  fetchedAt: string | null
}) {
  const { profile, summaries, latestSummary, currentSemesterSubjects } = data

  const department = profile.department_name ?? "No department assigned"

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl bg-card p-5 ring-1 ring-foreground/10">
        <div className="flex items-center gap-3.5">
          <AvatarInitials firstName={profile.first_name} lastName={profile.last_name} size="md" />
          <div>
            <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase">
              Student overview
            </p>
            <h1 className="text-2xl font-semibold tracking-tight">
              Welcome back, {profile.first_name}!
            </h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {department} · Semester {profile.current_semester} · Enrollment {profile.enrollment_no}
            </p>
          </div>
        </div>
        <FreshnessBadge fetchedAt={fetchedAt} />
      </section>

      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4" aria-label="Latest semester summary">
        <StatCard
          label="Latest SGPA"
          value={latestSummary ? latestSummary.sgpa.toFixed(2) : "—"}
          icon={Gauge}
          hint={latestSummary ? `Semester ${latestSummary.semester}` : "No data yet"}
        />
        <StatCard
          label="Attendance"
          value={latestSummary ? `${latestSummary.attendance_percentage.toFixed(1)}%` : "—"}
          icon={CalendarCheck}
          hint={latestSummary ? `Semester ${latestSummary.semester}` : "No data yet"}
          tone="success"
        />
        <StatCard
          label="Active backlogs"
          value={latestSummary ? String(latestSummary.active_backlogs) : "—"}
          icon={TriangleAlert}
          hint="Latest semester"
          tone={latestSummary ? (latestSummary.active_backlogs > 0 ? "warning" : "success") : undefined}
        />
        <StatCard
          label="Credits earned"
          value={latestSummary ? String(latestSummary.total_credits_earned) : "—"}
          icon={ListChecks}
          hint="Latest semester"
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2" aria-label="Academic trends">
        <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">SGPA trend</h2>
              <p className="text-xs text-muted-foreground">Semester-by-semester performance</p>
            </div>
            <Link
              href="/student/academic"
              className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              View academic <ArrowRight className="size-3" />
            </Link>
          </div>
          {summaries.length === 0 ? (
            <EmptyState
              icon={GraduationCap}
              title="No semester summaries yet"
              description="Your semester-by-semester SGPA will appear here once records are available."
            />
          ) : (
            <TrendChart
              data={summaries.map((item) => ({
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
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">Attendance trend</h2>
              <p className="text-xs text-muted-foreground">Semester-by-semester attendance</p>
            </div>
            <Link
              href="/student/attendance"
              className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              View attendance <ArrowRight className="size-3" />
            </Link>
          </div>
          {summaries.length === 0 ? (
            <EmptyState
              icon={CalendarCheck}
              title="No attendance records yet"
              description="Your attendance trend will appear here once records are available."
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
        </div>
      </section>

      <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Current-semester subjects</h2>
            <p className="text-xs text-muted-foreground">
              Performance for semester {profile.current_semester}
            </p>
          </div>
          <Link
            href="/student/subjects"
            className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            All subjects <ArrowRight className="size-3" />
          </Link>
        </div>
        {currentSemesterSubjects.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title="No subjects recorded this semester"
            description={`Subject performance for semester ${profile.current_semester} will appear here once records are available.`}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Code
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
                {currentSemesterSubjects.map((subject) => (
                  <tr
                    key={subject.subject_code}
                    className="border-b transition-colors last:border-0 hover:bg-muted/40"
                  >
                    <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">
                      {subject.subject_code}
                    </td>
                    <td className="py-2 pr-4 font-medium whitespace-nowrap">
                      {subject.subject_name}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {subject.total_marks !== null ? subject.total_marks.toFixed(1) : "—"}
                    </td>
                    <td className="py-2 pr-4 whitespace-nowrap">
                      <GradeBadge grade={subject.grade} />
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
        )}
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {[
          {
            href: "/student/academic",
            label: "Academic history",
            description: "Semester-by-semester SGPA, credits and backlogs.",
            icon: GraduationCap,
          },
          {
            href: "/student/subjects",
            label: "Subject performance",
            description: "Marks, grades and attendance per subject.",
            icon: BookOpen,
          },
          {
            href: "/student/attendance",
            label: "Attendance",
            description: "Semester and subject attendance records.",
            icon: CalendarCheck,
          },
        ].map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="group flex flex-col gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10 transition-colors outline-none hover:bg-muted/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <item.icon className="size-5 text-primary" />
            <div>
              <p className="text-sm font-medium">{item.label}</p>
              <p className="text-xs text-muted-foreground">{item.description}</p>
            </div>
            <ArrowRight className="ml-auto size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
          </Link>
        ))}
      </section>
    </div>
  )
}
