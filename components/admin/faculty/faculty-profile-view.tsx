"use client"

import {
  AlertTriangle,
  ArrowLeft,
  Award,
  BookOpen,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  Clock3,
  GraduationCap,
  Users,
} from "lucide-react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"

import type { AdminFacultyProfileData } from "@/lib/admin-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { AvatarInitials } from "@/components/shared/data/avatar-initials"
import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
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

function toFixed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—"
  return value.toFixed(digits)
}

function withSuffix(value: number | null | undefined, suffix: string): string {
  if (value === null || value === undefined) return "—"
  return `${toFixed(value)}${suffix}`
}

export function FacultyProfileView({
  data,
  fetchedAt,
}: {
  data: AdminFacultyProfileData
  fetchedAt: string
}) {
  const searchParams = useSearchParams()
  const backHref = `/admin/faculty${searchParams?.toString() ? `?${searchParams.toString()}` : ""}`

  const { faculty, teaching_overview, subjects, insights } = data
  const nameParts = faculty.full_name.trim().split(" ")
  const firstName = nameParts[0] ?? ""
  const lastName = nameParts.slice(1).join(" ")

  const gradeChartData = (insights.grade_distribution ?? []).map((item) => ({
    grade: item.grade,
    count: item.count,
  }))

  return (
    <div className="mx-auto flex max-w-full flex-col gap-6 lg:max-w-[95%]">
      {/* Back Navigation */}
      <div className="flex items-center gap-3">
        <Link
          href={backHref}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-4" />
          Back to Faculty
        </Link>
      </div>

      {/* Header */}
      <PageHeader
        title={faculty.full_name}
        description={`Faculty ID: ${faculty.faculty_id} • ${faculty.department_name} • Authoritative Profile & Teaching Allocations`}
        fetchedAt={fetchedAt}
      />

      {/* Identity Card */}
      <section className="flex flex-wrap items-center gap-4 rounded-xl bg-card p-5 ring-1 ring-foreground/10">
        <AvatarInitials firstName={firstName} lastName={lastName} size="lg" />
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-semibold tracking-tight">{faculty.full_name}</h2>
          <p className="text-sm text-muted-foreground">
            {faculty.faculty_id}
            {faculty.faculty_code ? ` • Code: ${faculty.faculty_code}` : ""}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {faculty.designation && <Badge variant="default">{faculty.designation}</Badge>}
            {faculty.department_name && <Badge variant="outline">{faculty.department_name}</Badge>}
            {faculty.status && (
              <Badge
                variant={faculty.status.toLowerCase() === "active" ? "secondary" : "muted"}
                className={
                  faculty.status.toLowerCase() === "active"
                    ? "bg-chart-2/15 text-chart-2"
                    : undefined
                }
              >
                {faculty.status}
              </Badge>
            )}
            {faculty.employment_type && (
              <Badge variant="muted">{faculty.employment_type}</Badge>
            )}
            {faculty.joining_date && (
              <Badge variant="muted">Joined {faculty.joining_date}</Badge>
            )}
          </div>
        </div>
      </section>

      {/* Academic / Teaching Overview KPIs */}
      <section
        className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6"
        aria-label="Teaching Overview"
      >
        <StatCard
          label="Subjects Taught"
          value={String(teaching_overview.total_subjects)}
          icon={BookOpen}
          tone="primary"
          hint="Distinct curriculum subjects"
        />
        <StatCard
          label="Students Handled"
          value={String(teaching_overview.active_students || teaching_overview.total_students_handled)}
          icon={Users}
          tone="success"
          hint="Enrolled in classes"
        />
        <StatCard
          label="Semesters"
          value={String(teaching_overview.total_semesters)}
          icon={GraduationCap}
          tone="primary"
          hint={
            teaching_overview.assigned_semesters.length > 0
              ? `Semesters: ${teaching_overview.assigned_semesters.join(", ")}`
              : "Semesters taught"
          }
        />
        <StatCard
          label="Workload"
          value={
            teaching_overview.workload_hours !== null
              ? `${toFixed(teaching_overview.workload_hours)} h/wk`
              : "—"
          }
          icon={Clock3}
          tone="warning"
          hint="Weekly teaching hours"
        />
        <StatCard
          label="Avg Class Marks"
          value={withSuffix(insights.overall_avg_marks, "%")}
          icon={Award}
          tone="primary"
          hint="Across evaluated students"
        />
        <StatCard
          label="Avg Attendance"
          value={withSuffix(insights.overall_avg_attendance, "%")}
          icon={CheckCircle2}
          tone="success"
          hint="Subject attendance average"
        />
      </section>

      {/* Faculty Details & Insights */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Employment & Personal Profile */}
        <section className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-2 text-base font-semibold flex items-center gap-2">
            <BriefcaseBusiness className="size-4 text-primary" />
            Faculty Information
          </h3>
          <p className="text-xs text-muted-foreground mb-4">
            Institutional employment record from authoritative backend store.
          </p>
          <dl>
            <DetailRow label="Faculty ID" value={faculty.faculty_id} />
            <DetailRow label="Faculty Code" value={faculty.faculty_code || "—"} />
            <DetailRow label="Department" value={faculty.department_name} />
            <DetailRow label="Designation" value={faculty.designation || "—"} />
            <DetailRow label="Qualification" value={faculty.qualification || "—"} />
            <DetailRow label="Specialization" value={faculty.specialization || "—"} />
            <DetailRow
              label="Experience"
              value={faculty.experience_years !== null ? `${faculty.experience_years} years` : "—"}
            />
            <DetailRow label="Email" value={faculty.email || "—"} />
            <DetailRow label="Phone Number" value={faculty.phone_number ? String(faculty.phone_number) : "—"} />
            <DetailRow label="Employment Type" value={faculty.employment_type || "—"} />
            <DetailRow label="Status" value={faculty.status || "—"} />
            <DetailRow label="Joining Date" value={faculty.joining_date || "—"} />
          </dl>
        </section>

        {/* Academic / Student Insights */}
        <section className="flex flex-col gap-4">
          <ChartCard
            title="Class Grade Distribution"
            subtitle={`Distribution of grades awarded across ${insights.total_evaluated_records} student evaluation records`}
            status={gradeChartData.length > 0 ? "ready" : "empty"}
            emptyIcon={Award}
            emptyTitle="No evaluation records"
            emptyDescription="There are no evaluated grades for this faculty member's classes."
          >
            <SubjectBarChart
              data={gradeChartData}
              xKey="grade"
              dataKey="count"
              color="var(--chart-1)"
              height={200}
            />
          </ChartCard>

          <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
            <h3 className="mb-2 text-base font-semibold flex items-center gap-2">
              <AlertTriangle className="size-4 text-chart-4" />
              Academic Risk & Performance Insights
            </h3>
            <div className="grid grid-cols-2 gap-4 mt-3">
              <div className="rounded-lg bg-muted/40 p-3">
                <p className="text-xs text-muted-foreground">Total Evaluated Records</p>
                <p className="text-xl font-bold mt-0.5 tabular-nums">
                  {insights.total_evaluated_records}
                </p>
              </div>
              <div className="rounded-lg bg-destructive/10 p-3">
                <p className="text-xs text-destructive font-medium">Students Needing Attention</p>
                <p className="text-xl font-bold mt-0.5 tabular-nums text-destructive">
                  {insights.total_at_risk_count}
                </p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Failing or below pass threshold (&lt;40%)
                </p>
              </div>
            </div>
            {teaching_overview.assigned_departments.length > 0 && (
              <div className="mt-4 pt-3 border-t border-border/60">
                <p className="text-xs text-muted-foreground">
                  <Building2 className="size-3.5 inline mr-1" />
                  Assigned Departments:{" "}
                  <span className="font-medium text-foreground">
                    {teaching_overview.assigned_departments.join(", ")}
                  </span>
                </p>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Subject / Class Information Table */}
      <ChartCard
        title="Subjects & Classes Taught"
        subtitle="Complete history of course allocations, enrollment counts, attendance averages, and class performance"
        status={subjects.length > 0 ? "ready" : "empty"}
        emptyIcon={BookOpen}
        emptyTitle="No subjects taught"
        emptyDescription="This faculty member currently has no subject allocations recorded."
        exportFileName={`faculty_${faculty.faculty_id}_subjects.csv`}
        exportColumns={[
          { key: "subject_code", label: "Subject Code" },
          { key: "subject_name", label: "Subject" },
          { key: "department_name", label: "Department" },
          { key: "semester_no", label: "Semester" },
          { key: "academic_year", label: "Academic Year" },
          { key: "student_count", label: "Students" },
          { key: "total_classes", label: "Total Classes" },
          { key: "avg_attendance", label: "Avg Attendance %" },
          { key: "avg_marks_pct", label: "Avg Marks %" },
          { key: "at_risk_count", label: "At-Risk Count" },
        ]}
        exportRows={subjects as unknown as Array<Record<string, unknown>>}
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-200 text-left text-sm">
            <thead>
              <tr className="border-b text-xs text-muted-foreground uppercase">
                <th className="py-2 pr-4 font-medium">Subject</th>
                <th className="py-2 pr-4 font-medium">Department</th>
                <th className="py-2 pr-4 text-right font-medium">Sem</th>
                <th className="py-2 pr-4 text-right font-medium">Academic Year</th>
                <th className="py-2 pr-4 text-right font-medium">Students</th>
                <th className="py-2 pr-4 text-right font-medium">Classes</th>
                <th className="py-2 pr-4 text-right font-medium">Avg Attendance</th>
                <th className="py-2 pr-4 text-right font-medium">Avg Marks</th>
                <th className="py-2 text-right font-medium">At Risk</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((sub, idx) => (
                <tr
                  key={`${sub.subject_id}-${sub.semester_no}-${sub.academic_year}-${idx}`}
                  className="border-b last:border-0 hover:bg-muted/30 transition-colors"
                >
                  <td className="py-2.5 pr-4">
                    <p className="max-w-64 truncate font-medium" title={sub.subject_name}>
                      {sub.subject_name}
                    </p>
                    <p className="text-xs text-muted-foreground">{sub.subject_code}</p>
                  </td>
                  <td className="py-2.5 pr-4 text-xs">{sub.department_name}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    {sub.semester_no ?? "—"}
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums text-xs">
                    {sub.academic_year ?? "—"}
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{sub.student_count}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    {sub.total_classes ?? "—"}
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    {withSuffix(sub.avg_attendance, "%")}
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    {withSuffix(sub.avg_marks_pct, "%")}
                  </td>
                  <td className="py-2.5 text-right tabular-nums">
                    {sub.at_risk_count > 0 ? (
                      <span className="inline-flex items-center rounded-md bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
                        {sub.at_risk_count}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">0</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartCard>
    </div>
  )
}
