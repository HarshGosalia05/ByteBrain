import {
  AlertTriangle,
  BookOpen,
  CalendarDays,
  ClipboardList,
  FileText,
  GraduationCap,
  Percent,
  TrendingUp,
} from "lucide-react"

import type { ReportCardResponse, ReportCardSemester } from "@/lib/student-api"

import { EmptyState } from "@/components/shared/state/empty-state"
import { StatCard } from "@/components/shared/data/stat-card"
import { Badge } from "@/components/ui/badge"

import { PrintButton } from "@/components/student/report-card/print-button"
import { PrintReportCard } from "@/components/student/report-card/print-report-card"

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

function StandingBadge({ standing }: { standing: string | null }) {
  if (standing === null) return <Badge variant="muted">—</Badge>
  const normalized = standing.toUpperCase()
  const variant =
    normalized === "GOOD"
      ? "success"
      : normalized === "PROBATION" || normalized === "RISK"
        ? "warning"
        : "secondary"
  return <Badge variant={variant}>{standing}</Badge>
}

function SemesterBlock({ semester }: { semester: ReportCardSemester }) {
  return (
    <section className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-sm font-semibold">
            Semester {semester.semester}
          </h2>
          {semester.academic_year && (
            <p className="text-xs text-muted-foreground">
              {semester.academic_year}
            </p>
          )}
        </div>
        <dl className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <dt className="sr-only">SGPA</dt>
            <GraduationCap className="size-3.5" />
            <dd className="font-medium text-foreground tabular-nums">
              SGPA {fmt(semester.sgpa, 2)}
            </dd>
          </div>
          <div className="flex items-center gap-1">
            <dt className="sr-only">Percentage</dt>
            <Percent className="size-3.5" />
            <dd className="font-medium text-foreground tabular-nums">
              {fmt(semester.semester_percentage, 2, "%")}
            </dd>
          </div>
          <div className="flex items-center gap-1">
            <dt className="sr-only">Attendance</dt>
            <CalendarDays className="size-3.5" />
            <dd className="font-medium text-foreground tabular-nums">
              {fmt(semester.attendance_percentage, 1, "%")}
            </dd>
          </div>
          <div className="flex items-center gap-1">
            <dt className="sr-only">Credits earned</dt>
            <BookOpen className="size-3.5" />
            <dd className="font-medium text-foreground tabular-nums">
              {fmt(semester.total_credits_earned, 0)} /{" "}
              {fmt(semester.credits_registered, 0)} credits
            </dd>
          </div>
          <div className="flex items-center gap-1">
            <dt className="sr-only">Backlogs</dt>
            <AlertTriangle className="size-3.5" />
            <dd className="font-medium text-foreground tabular-nums">
              {semester.active_backlogs === null
                ? "—"
                : `${semester.active_backlogs} backlog${semester.active_backlogs === 1 ? "" : "s"}`}
            </dd>
          </div>
          <div className="flex items-center gap-1">
            <dt className="sr-only">Grade</dt>
            <dd>
              <ResultBadge result={semester.semester_result} />
            </dd>
          </div>
        </dl>
      </div>

      {semester.subjects.length === 0 ? (
        <div className="p-6">
          <p className="text-sm text-muted-foreground">
            No subject records for this semester yet.
          </p>
        </div>
      ) : (
        <table className="w-full min-w-[840px] text-sm">
          <caption className="sr-only">
            Subject marks for semester {semester.semester}
          </caption>
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th scope="col" className="py-3 pr-4 pl-4 font-medium">
                Subject
              </th>
              <th scope="col" className="py-3 pr-4 text-right font-medium">
                Credits
              </th>
              <th scope="col" className="py-3 pr-4 text-right font-medium">
                Internal
              </th>
              <th scope="col" className="py-3 pr-4 text-right font-medium">
                Mid-sem
              </th>
              <th scope="col" className="py-3 pr-4 text-right font-medium">
                End-sem
              </th>
              <th scope="col" className="py-3 pr-4 text-right font-medium">
                Total
              </th>
              <th scope="col" className="py-3 pr-4 text-right font-medium">
                %
              </th>
              <th scope="col" className="py-3 pr-4 font-medium">
                Grade
              </th>
              <th scope="col" className="py-3 pr-4 font-medium">
                Result
              </th>
              <th scope="col" className="py-3 pr-4 text-right font-medium">
                Attendance
              </th>
            </tr>
          </thead>
          <tbody>
            {semester.subjects.map((subject) => (
              <tr
                key={`${semester.semester}-${subject.subject_code}`}
                className="border-b transition-colors last:border-0 hover:bg-muted/40"
              >
                <td className="py-3 pr-4 pl-4">
                  <span className="font-medium">{subject.subject_name}</span>
                  <span className="block text-xs text-muted-foreground">
                    {subject.subject_code}
                  </span>
                </td>
                <td className="py-3 pr-4 text-right tabular-nums">
                  {fmt(subject.credits, 0)}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums">
                  {fmt(subject.internal_marks, 2)}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums">
                  {fmt(subject.mid_sem_marks, 2)}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums">
                  {fmt(subject.end_sem_marks, 2)}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums">
                  {fmt(subject.total_marks, 2)}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums">
                  {fmt(subject.percentage, 2, "%")}
                </td>
                <td className="py-3 pr-4">
                  {subject.grade === null ? (
                    <Badge variant="muted">—</Badge>
                  ) : (
                    <Badge variant="secondary">{subject.grade}</Badge>
                  )}
                </td>
                <td className="py-3 pr-4">
                  <ResultBadge result={subject.result_status} />
                </td>
                <td className="py-3 pr-4 text-right tabular-nums">
                  {fmt(subject.attendance_percentage, 1, "%")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

export function ReportCardView({ data }: { data: ReportCardResponse }) {
  const { profile, semesters, generated_at } = data

  if (semesters.length === 0) {
    return (
      <div>
        <div className="screen-report-card">
          <EmptyState
            icon={ClipboardList}
            title="No report card data yet"
            description="Your consolidated report card will appear here once semester records are available."
          />
        </div>
        <PrintReportCard data={data} />
      </div>
    )
  }

  const fullName = `${profile.first_name} ${profile.last_name}`.trim()
  const standingTone =
    profile.academic_standing?.toUpperCase() === "GOOD"
      ? "success"
      : profile.academic_standing?.toUpperCase() === "PROBATION"
        ? "warning"
        : ("primary" as const)

  return (
    <div>
      <div className="screen-report-card">
        <div className="flex flex-col gap-6">
          <div className="flex justify-end print:hidden">
            <PrintButton />
          </div>

          <section className="rounded-xl bg-card p-6 ring-1 ring-foreground/10">
            <div className="flex flex-wrap items-start justify-between gap-6">
              <div>
                <p className="flex items-center gap-1.5 text-xs font-medium tracking-widest text-muted-foreground uppercase">
                  <FileText className="size-3.5" />
                  KenexAI · Academic Report
                </p>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight">
                  {fullName}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {profile.department_name ?? "Department not recorded"}
                </p>
              </div>
              <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-xs text-muted-foreground">
                    Enrollment No.
                  </dt>
                  <dd className="font-medium tabular-nums">
                    {profile.enrollment_no}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">
                    Current semester
                  </dt>
                  <dd className="font-medium">
                    {profile.current_semester === null
                      ? "—"
                      : `Semester ${profile.current_semester}`}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">
                    Academic year
                  </dt>
                  <dd className="font-medium">
                    {profile.current_academic_year ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">
                    Admission year
                  </dt>
                  <dd className="font-medium tabular-nums">
                    {profile.admission_year}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">
                    Generated on
                  </dt>
                  <dd className="font-medium tabular-nums">{generated_at}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Standing</dt>
                  <dd>
                    <StandingBadge standing={profile.academic_standing} />
                  </dd>
                </div>
              </dl>
            </div>
          </section>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <StatCard
              label="Overall CGPA"
              value={fmt(profile.overall_cgpa, 2)}
              icon={GraduationCap}
              hint="Cumulative grade point average"
            />
            <StatCard
              label="Overall Percentage"
              value={fmt(profile.overall_percentage, 2, "%")}
              icon={Percent}
              hint="Across all semesters"
            />
            <StatCard
              label="Latest SGPA"
              value={fmt(profile.latest_sgpa, 2)}
              icon={TrendingUp}
              hint={profile.current_academic_year ?? "Not available"}
            />
            <StatCard
              label="Credits earned"
              value={fmt(profile.total_credits_earned, 0)}
              icon={BookOpen}
              hint={`of ${fmt(profile.total_credits_registered, 0)} registered`}
            />
            <StatCard
              label="Backlogs"
              value={fmt(profile.total_backlogs, 0)}
              icon={AlertTriangle}
              hint="Active pending subjects"
              tone={
                profile.total_backlogs !== null && profile.total_backlogs > 0
                  ? "destructive"
                  : "success"
              }
            />
            <StatCard
              label="Academic standing"
              value={profile.academic_standing ?? "—"}
              icon={ClipboardList}
              hint="Current academic status"
              tone={standingTone}
            />
          </div>

          <div className="flex flex-col gap-6">
            {semesters.map((semester) => (
              <SemesterBlock key={semester.semester} semester={semester} />
            ))}
          </div>
        </div>
      </div>
      <PrintReportCard data={data} />
    </div>
  )
}
