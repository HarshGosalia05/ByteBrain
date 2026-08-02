import {
  BookOpen,
  CalendarCheck,
  Gauge,
  GraduationCap,
  TriangleAlert,
  Users,
} from "lucide-react"

import type { FacultyDashboardSummary } from "@/lib/faculty-api"

import { AvatarInitials } from "@/components/shared/data/avatar-initials"
import { FreshnessBadge } from "@/components/shared/data/freshness-badge"
import { StatCard } from "@/components/shared/data/stat-card"
import { EmptyState } from "@/components/shared/state/empty-state"
import { Badge } from "@/components/ui/badge"

function formatPercent(value: number | null, digits = 1): string {
  return value !== null ? `${value.toFixed(digits)}%` : "—"
}

export function DashboardView({
  data,
  fetchedAt,
}: {
  data: FacultyDashboardSummary
  fetchedAt: string | null
}) {
  const {
    full_name: fullName,
    designation,
    department_name: department,
    semester_no: semesterNo,
    academic_year: academicYear,
  } = data

  const firstName = fullName.split(" ")[0] ?? ""
  const lastName = fullName.split(" ").slice(1).join(" ") ?? ""

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl bg-card p-5 ring-1 ring-foreground/10">
        <div className="flex items-center gap-3.5">
          <AvatarInitials firstName={firstName} lastName={lastName} size="md" />
          <div>
            <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase">
              Faculty overview
            </p>
            <h1 className="text-2xl font-semibold tracking-tight">
              Welcome back, {firstName}!
            </h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {[designation, department].filter(Boolean).join(" · ") ||
                "Faculty member"}
              {semesterNo !== null && academicYear !== null
                ? ` · Teaching in Sem ${semesterNo} (${academicYear})`
                : ""}
            </p>
          </div>
        </div>
        <FreshnessBadge fetchedAt={fetchedAt} />
      </section>

      <section
        className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5"
        aria-label="Teaching overview"
      >
        <StatCard
          label="Subjects"
          value={String(data.subjects)}
          icon={BookOpen}
          hint={semesterNo !== null ? `Semester ${semesterNo}` : "No term yet"}
        />
        <StatCard
          label="Students"
          value={String(data.students)}
          icon={Users}
          hint="Across your classes"
          tone="success"
        />
        <StatCard
          label="Mentees"
          value={String(data.mentees)}
          icon={GraduationCap}
          hint="Under mentorship"
        />
        <StatCard
          label="Avg attendance"
          value={formatPercent(data.average_attendance)}
          icon={CalendarCheck}
          hint={semesterNo !== null ? `Semester ${semesterNo}` : "No data yet"}
        />
        <StatCard
          label="Avg performance"
          value={formatPercent(data.average_performance)}
          icon={Gauge}
          hint={semesterNo !== null ? `Semester ${semesterNo}` : "No data yet"}
        />
      </section>

      {data.needs_attention.length > 0 && (
        <section
          className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 ring-1 ring-destructive/10"
          aria-label="Needs attention"
        >
          <div className="mb-3 flex items-center gap-2">
            <TriangleAlert className="size-4 text-destructive" />
            <h2 className="text-sm font-semibold">Needs attention</h2>
            <p className="text-xs text-muted-foreground">
              Subjects below the configured performance or attendance threshold
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.needs_attention.map((item) => (
              <div
                key={item.subject_id}
                className="flex flex-col gap-1.5 rounded-lg bg-card p-3 ring-1 ring-foreground/10"
              >
                <p className="font-mono text-xs text-muted-foreground">{item.subject_code}</p>
                <p className="text-sm font-medium">{item.subject_name}</p>
                <div className="flex flex-wrap items-center gap-1.5">
                  {item.flags.includes("performance") && (
                    <Badge variant="destructive">Below performance baseline</Badge>
                  )}
                  {item.flags.includes("attendance") && (
                    <Badge variant="warning">Low attendance</Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground tabular-nums">
                  Performance {formatPercent(item.average_performance)} · Attendance{" "}
                  {formatPercent(item.average_attendance)}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Subjects this semester</h2>
            <p className="text-xs text-muted-foreground">
              {semesterNo !== null && academicYear !== null
                ? `Semester ${semesterNo} · ${academicYear}`
                : "No teaching assignments yet"}
            </p>
          </div>
        </div>
        {data.subject_breakdown.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title="No subjects assigned yet"
            description="Subjects you teach will appear here once teaching assignments are recorded."
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
                    Credits
                  </th>
                  <th scope="col" className="py-2 pr-4 text-right font-medium">
                    Students
                  </th>
                  <th scope="col" className="py-2 pr-4 text-right font-medium">
                    Avg attendance
                  </th>
                  <th scope="col" className="py-2 text-right font-medium">
                    Avg performance
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.subject_breakdown.map((subject) => (
                  <tr
                    key={subject.subject_id}
                    className="border-b transition-colors last:border-0 hover:bg-muted/40"
                  >
                    <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">
                      {subject.subject_code}
                    </td>
                    <td className="py-2 pr-4 font-medium whitespace-nowrap">
                      {subject.subject_name}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {subject.credits ?? "—"}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">{subject.students}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {formatPercent(subject.average_attendance)}
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      {formatPercent(subject.average_performance)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
