"use client"

import Link from "next/link"
import {
  ArrowLeft,
  BookOpen,
  CalendarCheck,
  Gauge,
  GraduationCap,
  TriangleAlert,
  Users,
} from "lucide-react"

import { SubjectBarChart } from "@/components/shared/charts/bar-chart"
import { TrendChart } from "@/components/shared/charts/trend-chart"
import { GradeBadge } from "@/components/shared/data/grade-badge"
import { StatCard } from "@/components/shared/data/stat-card"
import { EmptyState } from "@/components/shared/state/empty-state"
import { ErrorState } from "@/components/shared/state/error-state"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { FacultySubjectDetail, FacultySubjectHistory } from "@/lib/faculty-api"

function formatPercent(value: number | null, digits = 1): string {
  return value !== null ? `${value.toFixed(digits)}%` : "—"
}

export function SubjectDetail({
  detail,
  history,
  historyError,
}: {
  detail: FacultySubjectDetail
  history: FacultySubjectHistory | null
  historyError: string | null
}) {
  const gradeData = detail.grade_distribution.map((g) => ({ grade: g.grade, count: g.count }))
  const attendanceData = detail.attendance_distribution.map((a) => ({
    band: a.band,
    count: a.count,
  }))

  const trendData =
    history?.semesters_taught.map((h) => ({
      label: `Sem ${h.semester_no} · ${h.academic_year}`,
      average_performance: h.average_performance ?? 0,
      average_attendance: h.average_attendance ?? 0,
    })) ?? []

  const fullClassHref = `/faculty/students?tab=classes&subject_id=${detail.subject_id}&semester=${detail.semester_no}&academic_year=${encodeURIComponent(detail.academic_year)}`

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <Link
          href="/faculty/subjects"
          className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to Subjects
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-mono text-xs text-muted-foreground">{detail.subject_code}</p>
              <Badge variant="secondary">{detail.credits ?? "—"} credits</Badge>
            </div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">{detail.subject_name}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Sem {detail.semester_no} · {detail.academic_year}
              {detail.department_name ? ` · ${detail.department_name}` : ""}
            </p>
          </div>
          <span
            className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary"
          >
            Teaching now
          </span>
        </div>
      </section>

      {detail.learning_gap.flagged && (
        <section
          className="flex flex-wrap items-center gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4 ring-1 ring-destructive/10"
          role="alert"
        >
          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-destructive/10">
            <TriangleAlert className="size-4 text-destructive" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Below performance baseline</p>
            {detail.learning_gap.reason && (
              <p className="text-sm text-muted-foreground">{detail.learning_gap.reason}</p>
            )}
          </div>
        </section>
      )}

      <section
        className="grid grid-cols-2 gap-4 lg:grid-cols-5"
        aria-label="Subject overview"
      >
        <StatCard
          label="Total enrolled"
          value={detail.summary.total_enrolled.toString()}
          icon={Users}
          hint="Students in this class"
        />
        <StatCard
          label="Avg performance"
          value={formatPercent(detail.summary.average_percentage)}
          icon={Gauge}
          hint="Class average"
        />
        <StatCard
          label="Avg attendance"
          value={formatPercent(detail.summary.average_attendance)}
          icon={CalendarCheck}
          hint="Class average"
          tone="success"
        />
        <StatCard
          label="Pass rate"
          value={formatPercent(detail.summary.pass_percentage, 0)}
          icon={BookOpen}
          hint="Students passing this subject"
        />
        <StatCard
          label="Avg grade"
          value={detail.summary.average_grade ?? "—"}
          icon={GraduationCap}
          hint="Grade-point average"
        />
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
          <div className="mb-4">
            <h2 className="text-sm font-semibold">Performance distribution</h2>
            <p className="text-xs text-muted-foreground">
              Students by grade band for this subject
            </p>
          </div>
          {gradeData.length === 0 ? (
            <EmptyState
              icon={GraduationCap}
              title="No performance data yet"
              description="Grades will appear here once performance records are recorded."
            />
          ) : (
            <SubjectBarChart
              data={gradeData}
              xKey="grade"
              dataKey="count"
              color="var(--chart-1)"
            />
          )}
        </section>

        <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
          <div className="mb-4">
            <h2 className="text-sm font-semibold">Attendance distribution</h2>
            <p className="text-xs text-muted-foreground">
              Students grouped by attendance percentage
            </p>
          </div>
          {attendanceData.length === 0 ? (
            <EmptyState
              icon={CalendarCheck}
              title="No attendance data yet"
              description="Attendance records will appear here once recorded."
            />
          ) : (
            <SubjectBarChart
              data={attendanceData}
              xKey="band"
              dataKey="count"
              color="var(--chart-2)"
            />
          )}
        </section>
      </div>

      <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Enrolled students</h2>
            <p className="text-xs text-muted-foreground">
              {detail.summary.total_enrolled} students · Sem {detail.semester_no} ·{" "}
              {detail.academic_year}
            </p>
          </div>
          <Link href={fullClassHref} className={buttonVariants({ variant: "outline", size: "sm" })}>
            View full class
          </Link>
        </div>
        {detail.enrolled_students.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No students enrolled"
            description="Students enrolled in this subject will appear here."
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Enrollment No</TableHead>
                  <TableHead>Attendance</TableHead>
                  <TableHead>Performance</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {detail.enrolled_students.map((student) => (
                  <TableRow key={student.student_id}>
                    <TableCell className="font-medium">
                      {student.first_name} {student.last_name}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {student.enrollment_no}
                    </TableCell>
                    <TableCell>
                      {student.attendance_percentage !== null ? (
                        <span
                          className={
                            student.attendance_percentage < 75
                              ? "font-medium text-destructive"
                              : ""
                          }
                        >
                          {student.attendance_percentage.toFixed(1)}%
                        </span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>
                      {student.total_marks !== null ? (
                        <span className="flex items-center gap-2">
                          <span className="font-medium tabular-nums">{student.total_marks}</span>
                          <GradeBadge grade={student.grade} />
                        </span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <div className="mb-4">
          <h2 className="text-sm font-semibold">Historical view</h2>
          <p className="text-xs text-muted-foreground">
            How this subject has performed in each semester you taught it
          </p>
        </div>
        {historyError ? (
          <ErrorState title="Failed to load history" description={historyError} />
        ) : history && history.semesters_taught.length > 1 ? (
          <div className="flex flex-col gap-6">
            <TrendChart
              data={trendData}
              xKey="label"
              series={[
                { key: "average_performance", label: "Avg performance", color: "var(--chart-1)" },
                { key: "average_attendance", label: "Avg attendance", color: "var(--chart-2)" },
              ]}
              yDomain={[0, 100]}
              yTickSuffix="%"
            />
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Semester</TableHead>
                    <TableHead>Academic Year</TableHead>
                    <TableHead>Students</TableHead>
                    <TableHead>Avg Performance</TableHead>
                    <TableHead>Avg Attendance</TableHead>
                    <TableHead>Pass Rate</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.semesters_taught.map((item) => (
                    <TableRow key={`${item.semester_no}-${item.academic_year}`}>
                      <TableCell className="font-medium">{item.semester_no}</TableCell>
                      <TableCell>{item.academic_year}</TableCell>
                      <TableCell className="tabular-nums">{item.students}</TableCell>
                      <TableCell className="tabular-nums">
                        {formatPercent(item.average_performance)}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatPercent(item.average_attendance)}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatPercent(item.pass_percentage, 0)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        ) : history ? (
          <EmptyState
            icon={BookOpen}
            title="First semester teaching this subject"
            description="You are teaching this subject for the first time. A semester-by-semester comparison will appear here once you teach it again."
          />
        ) : null}
      </section>
    </div>
  )
}
