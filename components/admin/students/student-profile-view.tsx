"use client"

import {
  ArrowLeft,
  BookOpen,
  CalendarCheck,
  GraduationCap,
  Gauge,
  ListChecks,
  ShieldAlert,
  TrendingUp,
  TriangleAlert,
  Trophy,
  Zap,
} from "lucide-react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"

import type { AdminStudentProfileData } from "@/lib/admin-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { AvatarInitials } from "@/components/shared/data/avatar-initials"
import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
import { TrendChart } from "@/components/shared/charts/trend-chart"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"
import { Badge } from "@/components/ui/badge"

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-border/60 py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium tabular-nums">{value}</dd>
    </div>
  )
}

const RISK_STYLES: Record<string, string> = {
  Low: "bg-chart-2/15 text-chart-2",
  Moderate: "bg-chart-3/20 text-chart-3",
  High: "bg-chart-4/20 text-chart-4",
  Critical: "bg-destructive/10 text-destructive",
}

function toFixed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—"
  return value.toFixed(digits)
}

function withSuffix(value: number | null | undefined, suffix: string): string {
  if (value === null || value === undefined) return "—"
  return `${toFixed(value)}${suffix}`
}

export function StudentProfileView({
  data,
  fetchedAt,
}: {
  data: AdminStudentProfileData
  fetchedAt: string
}) {
  const searchParams = useSearchParams()
  const backHref = `/admin/students${searchParams.toString() ? `?${searchParams.toString()}` : ""}`

  const { student, academic, semesters, performance, risk, career } = data
  const fullName = `${student.first_name} ${student.last_name}`.trim()

  const strongestSubjects = performance
    .filter((p) => p.percentage !== null && p.percentage >= 80)
    .slice(0, 5)

  const attentionSubjects = performance
    .filter((p) => p.percentage !== null && p.percentage < 50)
    .slice(0, 5)

  const gradeData = performance.reduce<Record<string, number>>((acc, p) => {
    const grade = p.grade ?? "N/A"
    acc[grade] = (acc[grade] ?? 0) + 1
    return acc
  }, {})

  const gradeChartData = Object.entries(gradeData).map(([grade, count]) => ({
    grade,
    count,
  }))

  return (
    <div className="mx-auto flex max-w-full flex-col gap-6 lg:max-w-[95%]">
      <div className="flex items-center gap-3">
        <Link
          href={backHref}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-4" />
          Back to Students
        </Link>
      </div>

      <PageHeader
        title={fullName}
        description={`Student profile for ${student.student_id}`}
        fetchedAt={fetchedAt}
      />

      <section className="flex flex-wrap items-center gap-4 rounded-xl bg-card p-5 ring-1 ring-foreground/10">
        <AvatarInitials
          firstName={student.first_name}
          lastName={student.last_name}
          size="lg"
        />
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-semibold tracking-tight">{fullName}</h2>
          <p className="text-sm text-muted-foreground">{student.student_id}</p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <Badge variant="default">Semester {student.current_semester}</Badge>
            {student.department_name && (
              <Badge variant="outline">{student.department_name}</Badge>
            )}
            <Badge variant="muted">Batch {student.admission_year}</Badge>
            {student.enrollment_no && (
              <Badge variant="muted">Enrollment {student.enrollment_no}</Badge>
            )}
          </div>
        </div>
      </section>

      <section
        className="grid grid-cols-2 gap-4 lg:grid-cols-4"
        aria-label="Academic statistics"
      >
        <StatCard
          label="Current SGPA"
          value={toFixed(academic.latest_sgpa)}
          icon={Gauge}
          hint={`Semester ${student.current_semester}`}
        />
        <StatCard
          label="Overall CGPA"
          value={toFixed(academic.overall_cgpa)}
          icon={GraduationCap}
          hint="Cumulative"
        />
        <StatCard
          label="Overall Percentage"
          value={withSuffix(academic.overall_percentage, "%")}
          icon={TrendingUp}
        />
        <StatCard
          label="Total Backlogs"
          value={String(academic.total_backlogs ?? 0)}
          icon={TriangleAlert}
          tone={(academic.total_backlogs ?? 0) > 0 ? "warning" : "success"}
        />
      </section>

      <section
        className="grid grid-cols-2 gap-4 lg:grid-cols-4"
        aria-label="Additional statistics"
      >
        <StatCard
          label="Credits Earned"
          value={String(academic.total_credits_earned ?? 0)}
          icon={ListChecks}
          hint={`Registered: ${academic.total_credits_registered ?? "—"}`}
          tone="success"
        />
        <StatCard
          label="Academic Standing"
          value={academic.academic_standing ?? "—"}
          icon={Trophy}
          tone={
            academic.academic_standing === "Good"
              ? "success"
              : academic.academic_standing === "Probation"
                ? "warning"
                : "primary"
          }
        />
        <StatCard
          label="Risk Level"
          value={risk?.risk_level ?? "N/A"}
          icon={ShieldAlert}
          hint={
            risk?.risk_probability != null
              ? `${(risk.risk_probability * 100).toFixed(1)}%`
              : "No prediction"
          }
          tone={
            risk?.risk_level === "Critical"
              ? "warning"
              : risk?.risk_level === "High"
                ? "warning"
                : "primary"
          }
        />
        <StatCard
          label="Career Readiness"
          value={career?.score != null ? `${career.score}%` : "N/A"}
          icon={Zap}
          hint={career?.score != null ? "M4 score" : "No prediction"}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2" aria-label="Student details">
        <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-2 text-sm font-semibold">Personal Information</h3>
          <dl>
            <DetailRow label="Full Name" value={fullName} />
            <DetailRow label="Student ID" value={student.student_id} />
            <DetailRow
              label="Enrollment Number"
              value={String(student.enrollment_no)}
            />
            <DetailRow
              label="Department"
              value={student.department_name ?? "Not assigned"}
            />
            <DetailRow
              label="Starting Batch"
              value={String(student.admission_year)}
            />
            <DetailRow
              label="Current Semester"
              value={`Semester ${student.current_semester}`}
            />
          </dl>
        </div>

        <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-2 text-sm font-semibold">Academic Overview</h3>
          <dl>
            <DetailRow
              label="Latest SGPA"
              value={toFixed(academic.latest_sgpa)}
            />
            <DetailRow
              label="Overall CGPA"
              value={toFixed(academic.overall_cgpa)}
            />
            <DetailRow
              label="Overall Percentage"
              value={withSuffix(academic.overall_percentage, "%")}
            />
            <DetailRow
              label="Credits Earned"
              value={String(academic.total_credits_earned ?? 0)}
            />
            <DetailRow
              label="Total Backlogs"
              value={String(academic.total_backlogs ?? 0)}
            />
            <DetailRow
              label="Academic Standing"
              value={academic.academic_standing ?? "—"}
            />
          </dl>
        </div>
      </section>

      {risk && (
        <section className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-3 text-sm font-semibold">Risk &amp; Early Warning</h3>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <div>
              <p className="text-xs text-muted-foreground">Risk Band</p>
              <span
                className={`mt-1 inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                  RISK_STYLES[risk.risk_level ?? ""] ?? "bg-muted text-muted-foreground"
                }`}
              >
                {risk.risk_level ?? "N/A"}
              </span>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Probability</p>
              <p className="mt-1 text-sm font-medium tabular-nums">
                {risk.risk_probability != null
                  ? `${(risk.risk_probability * 100).toFixed(1)}%`
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Model Version</p>
              <p className="mt-1 text-sm font-medium">
                {risk.model_version ?? "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Prediction Time</p>
              <p className="mt-1 text-sm font-medium">
                {risk.generated_at
                  ? new Date(risk.generated_at).toLocaleDateString()
                  : "—"}
              </p>
            </div>
          </div>
        </section>
      )}

      {career && (
        <section className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-3 text-sm font-semibold">Career Readiness</h3>
          <div className="grid gap-4 lg:grid-cols-3">
            <div>
              <p className="text-xs text-muted-foreground">Score</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">
                {career.score != null ? `${career.score}%` : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Strengths</p>
              <ul className="mt-1 space-y-1">
                {(career.strengths ?? []).length > 0 ? (
                  career.strengths.map((s, i) => (
                    <li key={i} className="text-sm">
                      {s}
                    </li>
                  ))
                ) : (
                  <li className="text-sm text-muted-foreground">—</li>
                )}
              </ul>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Areas to Improve</p>
              <ul className="mt-1 space-y-1">
                {(career.areas_to_improve ?? []).length > 0 ? (
                  career.areas_to_improve.map((a, i) => (
                    <li key={i} className="text-sm">
                      {a}
                    </li>
                  ))
                ) : (
                  <li className="text-sm text-muted-foreground">—</li>
                )}
              </ul>
            </div>
          </div>
        </section>
      )}

      <section className="grid gap-4 lg:grid-cols-2" aria-label="Semester performance">
        <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
          <h3 className="mb-1 text-sm font-semibold">SGPA by Semester</h3>
          <p className="mb-4 text-xs text-muted-foreground">
            Grade point average per semester
          </p>
          {semesters.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <TrendChart
              data={semesters.map((s) => ({
                semester: `Sem ${s.semester}`,
                sgpa: s.sgpa ?? 0,
              }))}
              xKey="semester"
              series={[{ key: "sgpa", label: "SGPA", color: "var(--chart-1)" }]}
              yDomain={[0, 10]}
            />
          )}
        </div>

        <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
          <h3 className="mb-1 text-sm font-semibold">Attendance by Semester</h3>
          <p className="mb-4 text-xs text-muted-foreground">
            Semester-wise attendance percentage
          </p>
          {semesters.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <TrendChart
              data={semesters.map((s) => ({
                semester: `Sem ${s.semester}`,
                attendance: s.attendance_percentage ?? 0,
              }))}
              xKey="semester"
              series={[
                {
                  key: "attendance",
                  label: "Attendance %",
                  color: "var(--chart-2)",
                },
              ]}
              yDomain={[0, 100]}
              yTickSuffix="%"
            />
          )}
        </div>
      </section>

      {gradeChartData.length > 0 && (
        <ChartCard
          title="Grade Distribution"
          subtitle="Subject grades across all semesters"
          status="ready"
        >
          <SubjectBarChart
            data={[gradeChartData.reduce<Record<string, string | number>>(
              (acc, item) => {
                acc[item.grade] = item.count
                return acc
              },
              { label: "Grades" },
            )]}
            xKey="label"
            height={200}
            bars={gradeChartData.map((item) => ({
              dataKey: item.grade,
              name: item.grade,
              color: "var(--chart-1)",
            }))}
          />
        </ChartCard>
      )}

      {performance.length > 0 && (
        <section className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-2 text-sm font-semibold">Subject Performance</h3>
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
                {performance.map((subject, idx) => (
                  <tr
                    key={`${subject.semester}-${subject.subject_code}-${idx}`}
                    className="border-b transition-colors last:border-0 hover:bg-muted/40"
                  >
                    <td className="py-2 pr-4 text-muted-foreground whitespace-nowrap">
                      Sem {subject.semester}
                    </td>
                    <td className="py-2 pr-4 font-medium whitespace-nowrap">
                      {subject.subject_name}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {subject.total_marks !== null
                        ? subject.total_marks.toFixed(1)
                        : "—"}
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

      {strongestSubjects.length > 0 && (
        <section className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-2 text-sm font-semibold">Strong Subjects</h3>
          <p className="mb-3 text-xs text-muted-foreground">
            Subjects with 80% or above.
          </p>
          <div className="flex flex-wrap gap-2">
            {strongestSubjects.map((s, i) => (
              <Badge key={i} variant="outline">
                {s.subject_name} ({withSuffix(s.percentage, "%")})
              </Badge>
            ))}
          </div>
        </section>
      )}

      {attentionSubjects.length > 0 && (
        <section className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-2 text-sm font-semibold">Subjects Needing Attention</h3>
          <p className="mb-3 text-xs text-muted-foreground">
            Subjects with below 50%.
          </p>
          <div className="flex flex-wrap gap-2">
            {attentionSubjects.map((s, i) => (
              <Badge key={i} variant="destructive">
                {s.subject_name} ({withSuffix(s.percentage, "%")})
              </Badge>
            ))}
          </div>
        </section>
      )}

      <p className="text-xs text-muted-foreground">
        Data refreshed{" "}
        {fetchedAt ? new Date(fetchedAt).toLocaleString() : "just now"}
      </p>
    </div>
  )
}
