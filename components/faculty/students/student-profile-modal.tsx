"use client"

import * as React from "react"
import Link from "next/link"
import {
  AlertTriangle,
  Award,
  Book,
  BookCheck,
  BookOpen,
  BrainCircuit,
  CalendarClock,
  ClipboardList,
  Download,
  GraduationCap,
  Medal,
  MessageSquare,
  Percent,
  Printer,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
} from "lucide-react"

import { cn } from "@/lib/utils"
import type {
  FacultyStudentProfileSubject,
  FacultyStudentProfileView,
} from "@/lib/faculty-api"
import { fetchStudentProfileAction } from "@/app/faculty/students/actions"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { StatCard, type StatCardTone } from "@/components/shared/data/stat-card"
import { AvatarInitials } from "@/components/shared/data/avatar-initials"
import { TrendChart } from "@/components/shared/charts/trend-chart"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"
import { EmptyState } from "@/components/shared/state/empty-state"
import { LoadingSkeleton } from "@/components/shared/state/loading-skeleton"

const PRINT_STYLES = `
@media print {
  body * { visibility: hidden !important; }
  [data-print-area], [data-print-area] * { visibility: visible !important; }
  [data-print-area] { position: fixed !important; inset: 0 !important; overflow: visible !important; width: 100% !important; }
}
`

function fmt(v: number | null | undefined, digits = 1): string {
  return v == null || Number.isNaN(v) ? "—" : v.toFixed(digits)
}

function fmtPct(v: number | null | undefined): string {
  return v == null ? "—" : `${v.toFixed(1)}%`
}

function sgpaTone(v: number | null): StatCardTone {
  if (v == null) return "primary"
  if (v >= 8.5) return "success"
  if (v >= 7) return "warning"
  return "destructive"
}

function attendanceTone(v: number | null): StatCardTone {
  if (v == null) return "primary"
  if (v >= 85) return "success"
  if (v >= 75) return "warning"
  return "destructive"
}

function backlogsTone(v: number | null): StatCardTone {
  if (v == null) return "primary"
  if (v === 0) return "success"
  if (v <= 2) return "warning"
  return "destructive"
}

function rankTone(rank: number | null, total: number | null): StatCardTone {
  if (rank == null || !total) return "primary"
  const pct = rank / total
  if (pct <= 0.2) return "success"
  if (pct <= 0.5) return "warning"
  return "destructive"
}

function creditTone(earned: number | null, registered: number | null): StatCardTone {
  if (earned == null || !registered) return "primary"
  const ratio = earned / registered
  if (ratio >= 0.9) return "success"
  if (ratio >= 0.7) return "warning"
  return "destructive"
}

type SubjectTone = "success" | "warning" | "destructive" | "muted"

function subjectTone(sub: FacultyStudentProfileSubject): SubjectTone {
  const grade = sub.grade?.toUpperCase() ?? ""
  const failed =
    sub.result_status?.toLowerCase() === "fail" ||
    ["F", "FAIL", "ATKT", "RE-APPEAR", "BACKLOG"].includes(grade)
  if (failed) return "destructive"
  if (sub.percentage == null) return "muted"
  if (sub.percentage < 40) return "destructive"
  if (sub.percentage < 60) return "warning"
  return "success"
}

function isPoorSubject(sub: FacultyStudentProfileSubject): boolean {
  return subjectTone(sub) === "destructive"
}

function buildInsights(p: FacultyStudentProfileView): Array<{ tone: StatCardTone; text: string }> {
  const s = p.student
  const semesters = p.semester_summaries
  const insights: Array<{ tone: StatCardTone; text: string }> = []

  if (semesters.length >= 2) {
    const last = semesters[semesters.length - 1]?.semester_sgpa
    const prev = semesters[semesters.length - 2]?.semester_sgpa
    if (last != null && prev != null) {
      if (last > prev) {
        insights.push({ tone: "success", text: `SGPA improved from ${fmt(prev, 2)} to ${fmt(last, 2)} in the latest semester.` })
      } else if (last < prev) {
        insights.push({ tone: "warning", text: `SGPA dipped from ${fmt(prev, 2)} to ${fmt(last, 2)} in the latest semester — worth a follow-up.` })
      } else {
        insights.push({ tone: "success", text: `SGPA held steady at ${fmt(last, 2)} across the recent semesters.` })
      }
    }
  }

  if (s.overall_attendance_percentage != null) {
    const att = s.overall_attendance_percentage
    if (att < 75) {
      insights.push({ tone: "destructive", text: `Overall attendance is ${fmt(att, 1)}% — below the 75% threshold.` })
    } else if (att < 85) {
      insights.push({ tone: "warning", text: `Attendance is ${fmt(att, 1)}% — within range but needs monitoring.` })
    } else {
      insights.push({ tone: "success", text: `Consistent attendance at ${fmt(att, 1)}%.` })
    }
  }

  if (s.total_backlogs != null) {
    if (s.total_backlogs > 0) {
      insights.push({ tone: "destructive", text: `${s.total_backlogs} active backlog(s) on record — consider scheduling a catch-up plan.` })
    } else {
      insights.push({ tone: "success", text: "No active backlogs — the student is academically on-track." })
    }
  }

  if (p.rank != null && p.rank_total) {
    const pct = (p.rank / p.rank_total) * 100
    if (pct <= 20) {
      insights.push({ tone: "success", text: `Ranked #${p.rank} of ${p.rank_total} in the department — top ${Math.round(pct)}%.` })
    } else if (pct <= 50) {
      insights.push({ tone: "warning", text: `Ranked #${p.rank} of ${p.rank_total} in the department — middle of the pack.` })
    } else {
      insights.push({ tone: "destructive", text: `Ranked #${p.rank} of ${p.rank_total} in the department — in the lower half.` })
    }
  }

  return insights
}

function downloadProfileCsv(p: FacultyStudentProfileView) {
  const s = p.student
  const rows: Array<Array<string | number | null | undefined>> = [
    ["Field", "Value"],
    ["Student Name", s.full_name],
    ["Enrollment No", s.enrollment_no],
    ["University Roll No", s.university_roll_no],
    ["Department", s.department_name],
    ["Current Semester", s.current_semester],
    ["Academic Year", s.current_academic_year],
    ["Email", s.email],
    ["Phone", s.student_phone_number],
    ["City", s.city],
    ["Guardian", s.guardian_name],
    ["Latest SGPA", s.latest_sgpa],
    ["CGPA", s.overall_cgpa],
    ["Overall Percentage", s.overall_percentage],
    ["Attendance", s.overall_attendance_percentage],
    ["Credits Earned", s.total_credits_earned],
    ["Credits Registered", s.total_credits_registered],
    ["Backlogs", s.total_backlogs],
    ["Academic Standing", s.academic_standing],
    ["Department Rank", p.rank != null ? `#${p.rank} of ${p.rank_total ?? "-"}` : ""],
  ]
  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\n")
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `${s.full_name.replace(/\s+/g, "_")}_profile.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

const toneDot: Record<StatCardTone, string> = {
  primary: "bg-primary",
  success: "bg-chart-2",
  warning: "bg-chart-3",
  destructive: "bg-destructive",
}

const subjectBadgeVariant: Record<SubjectTone, "success" | "warning" | "destructive" | "muted"> = {
  success: "success",
  warning: "warning",
  destructive: "destructive",
  muted: "muted",
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="text-sm font-semibold tracking-widest text-muted-foreground uppercase">
      {children}
    </h4>
  )
}

function InfoGrid({ items }: { items: Array<{ label: string; value: React.ReactNode }> }) {
  return (
    <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => (
        <div key={item.label} className="flex min-w-0 flex-col gap-0.5">
          <span className="text-xs text-muted-foreground">{item.label}</span>
          <span className="truncate text-sm font-medium text-foreground">{item.value || "—"}</span>
        </div>
      ))}
    </div>
  )
}

export function StudentProfileModal({
  studentId,
  onClose,
}: {
  studentId: string | null
  onClose: () => void
}) {
  const [data, setData] = React.useState<FacultyStudentProfileView | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [activeTab, setActiveTab] = React.useState("overview")
  const [prevStudentId, setPrevStudentId] = React.useState(studentId)
  const scrollRef = React.useRef<HTMLDivElement>(null)

  if (studentId !== prevStudentId) {
    setPrevStudentId(studentId)
    setData(null)
    setError(null)
    setLoading(true)
  }

  React.useEffect(() => {
    if (!studentId) return

    let isMounted = true
    fetchStudentProfileAction(studentId).then((res) => {
      if (!isMounted) return
      if (res.ok) {
        setData(res.data)
      } else {
        setError(res.error.message)
      }
      setLoading(false)
    })

    return () => {
      isMounted = false
    }
  }, [studentId])

  const handleTabChange = (value: string) => {
    setActiveTab(value)
    scrollRef.current?.scrollTo({ top: 0 })
  }

  const s = data?.student
  const insights = data ? buildInsights(data) : []

  const subjectRows =
    data?.subject_performance.filter(
      (sub) => sub.attendance_percentage != null || sub.total_classes != null
    ) ?? []
  const poorSubjects =
    data?.subject_performance.filter((sub) => isPoorSubject(sub)) ?? []

  return (
    <>
      <style>{PRINT_STYLES}</style>
      <Dialog
        open={!!studentId}
        onOpenChange={(open) => {
          if (!open) onClose()
        }}
      >
        <DialogContent className="flex h-dvh max-h-dvh w-full max-w-full flex-col gap-0 overflow-hidden rounded-none border-0 p-0 sm:h-auto sm:max-h-[90dvh] sm:max-w-[90%] sm:rounded-xl sm:border sm:border-border lg:max-w-[1100px]">
          <div className="flex shrink-0 items-center justify-between gap-4 border-b px-6 py-4 pr-12">
            <div className="flex min-w-0 items-center gap-3">
              {data && s ? (
                <AvatarInitials firstName={s.first_name} lastName={s.last_name} size="md" />
              ) : (
                <Skeleton className="size-10 shrink-0 rounded-full" />
              )}
              <div className="flex min-w-0 flex-col gap-0.5">
                <DialogTitle className="truncate text-lg font-semibold">
                  {data && s ? s.full_name : "Student Profile"}
                </DialogTitle>
                <DialogDescription className="truncate">
                  {data && s
                    ? `${s.enrollment_no} • Semester ${s.current_semester ?? "-"} • ${s.department_name ?? "—"}`
                    : "Loading student details"}
                </DialogDescription>
              </div>
            </div>
            {data && studentId && (
              <div className="flex shrink-0 items-center gap-2">
                <Badge
                  variant={
                    data.relationship === "mentor"
                      ? "success"
                      : data.relationship === "class"
                        ? "outline"
                        : "muted"
                  }
                  className="hidden shrink-0 sm:inline-flex"
                >
                  {data.relationship}
                </Badge>
                <Link
                  href={`/faculty/students/${encodeURIComponent(studentId)}/ml-insights`}
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  <BrainCircuit aria-hidden="true" />
                  ML Insights
                </Link>
              </div>
            )}
          </div>

          {loading ? (
            <div className="flex-1 overflow-y-auto p-6">
              <LoadingSkeleton />
            </div>
          ) : error ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
              <div className="flex size-11 items-center justify-center rounded-full bg-destructive/10">
                <AlertTriangle className="size-5 text-destructive" />
              </div>
              <p className="text-sm font-medium text-destructive">{error}</p>
              <Button variant="outline" onClick={onClose}>
                Close
              </Button>
            </div>
          ) : data && s ? (
            <>
              <Tabs
                value={activeTab}
                onValueChange={handleTabChange}
                className="flex min-h-0 flex-1 flex-col gap-0"
              >
                <div className="shrink-0 overflow-x-auto border-b px-6 pt-2">
                  <TabsList className="h-9 rounded-t-lg rounded-b-none bg-transparent p-0">
                    <TabsTrigger value="overview" className="rounded-lg data-[selected]:bg-muted data-[selected]:ring-0">Overview</TabsTrigger>
                    <TabsTrigger value="academics" className="rounded-lg data-[selected]:bg-muted data-[selected]:ring-0">Academics</TabsTrigger>
                    <TabsTrigger value="attendance" className="rounded-lg data-[selected]:bg-muted data-[selected]:ring-0">Attendance</TabsTrigger>
                    <TabsTrigger value="performance" className="rounded-lg data-[selected]:bg-muted data-[selected]:ring-0">Performance</TabsTrigger>
                    <TabsTrigger value="skills" className="rounded-lg data-[selected]:bg-muted data-[selected]:ring-0">Skills</TabsTrigger>
                    <TabsTrigger value="placement" className="rounded-lg data-[selected]:bg-muted data-[selected]:ring-0">Placement</TabsTrigger>
                  </TabsList>
                </div>

                <div ref={scrollRef} data-print-area className="min-h-0 flex-1 overflow-y-auto p-6">
                  <TabsContent value="overview" className="mt-0">
                    <div className="flex flex-col gap-6">
                      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                        <StatCard
                          label="Latest SGPA"
                          value={fmt(s.latest_sgpa, 2)}
                          icon={GraduationCap}
                          tone={sgpaTone(s.latest_sgpa)}
                          hint={s.current_semester ? `Semester ${s.current_semester}` : undefined}
                        />
                        <StatCard
                          label="CGPA"
                          value={fmt(s.overall_cgpa, 2)}
                          icon={Award}
                          tone={sgpaTone(s.overall_cgpa)}
                          hint={s.overall_percentage != null ? `${fmt(s.overall_percentage, 2)}% overall` : undefined}
                        />
                        <StatCard
                          label="Attendance"
                          value={fmtPct(s.overall_attendance_percentage)}
                          icon={Percent}
                          tone={attendanceTone(s.overall_attendance_percentage)}
                          hint="vs 75% minimum"
                        />
                        <StatCard
                          label="Backlogs"
                          value={s.total_backlogs == null ? "—" : String(s.total_backlogs)}
                          icon={Book}
                          tone={backlogsTone(s.total_backlogs)}
                        />
                        <StatCard
                          label="Credits Earned"
                          value={`${s.total_credits_earned ?? 0}/${s.total_credits_registered ?? 0}`}
                          icon={BookCheck}
                          tone={creditTone(s.total_credits_earned, s.total_credits_registered)}
                        />
                        <StatCard
                          label="Department Rank"
                          value={data.rank != null ? `#${data.rank}` : "—"}
                          icon={Medal}
                          tone={rankTone(data.rank, data.rank_total)}
                          hint={data.rank_total ? `of ${data.rank_total} students` : undefined}
                        />
                      </div>

                      <div className="rounded-xl bg-muted/30 p-5 ring-1 ring-foreground/10">
                        <div className="flex items-center gap-2">
                          <BrainCircuit className="size-4 text-muted-foreground" />
                          <SectionTitle>Faculty Insights</SectionTitle>
                        </div>
                        {insights.length > 0 ? (
                          <ul className="mt-3 flex flex-col gap-2">
                            {insights.map((insight, index) => (
                              <li key={index} className="flex items-start gap-2 text-sm">
                                <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", toneDot[insight.tone])} aria-hidden="true" />
                                <span className="text-foreground/90">{insight.text}</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-3 text-sm text-muted-foreground">
                            No observations available yet.
                          </p>
                        )}
                      </div>

                      <div className="flex flex-col gap-3">
                        <SectionTitle>Student Overview</SectionTitle>
                        <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
                          <InfoGrid
                            items={[
                              { label: "Enrollment No", value: s.enrollment_no },
                              { label: "University Roll No", value: s.university_roll_no },
                              { label: "Gender", value: s.gender },
                              { label: "Date of Birth", value: s.date_of_birth },
                              { label: "Category", value: s.category },
                              { label: "Department", value: s.department_name },
                              { label: "Semester", value: s.current_semester },
                              { label: "Academic Year", value: s.current_academic_year },
                              { label: "Student Status", value: s.student_status },
                              { label: "City", value: s.city },
                              { label: "Email", value: s.email },
                              { label: "Phone", value: s.student_phone_number },
                              { label: "Guardian", value: s.guardian_name },
                              { label: "Guardian Phone", value: s.guardian_phone },
                              { label: "Admission Year", value: s.admission_year },
                              { label: "Admission Date", value: s.admission_date },
                              { label: "Admission Type", value: s.admission_type },
                              { label: "Admission Quota", value: s.admission_quota },
                            ]}
                          />
                        </div>
                      </div>

                      {data.mentor && (
                        <div className="flex flex-col gap-3">
                          <SectionTitle>Mentor</SectionTitle>
                          <div className="flex items-start gap-3 rounded-xl bg-card p-5 ring-1 ring-foreground/10">
                            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-chart-2/15 text-chart-2">
                              <Users className="size-4" />
                            </div>
                            <div className="flex flex-col gap-1">
                              <p className="text-sm font-semibold">{data.mentor.faculty_name}</p>
                              <p className="text-sm text-muted-foreground">
                                {[data.mentor.designation, data.mentor.mentor_role]
                                  .filter(Boolean)
                                  .join(" • ") || "Faculty Mentor"}
                              </p>
                              {data.mentor.mentor_since && (
                                <p className="text-xs text-muted-foreground">
                                  Mentor since {data.mentor.mentor_since}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </TabsContent>

                  <TabsContent value="academics" className="mt-0">
                    <div className="flex flex-col gap-6">
                      <div className="flex flex-col gap-3">
                        <SectionTitle>Academic Timeline</SectionTitle>
                        {data.semester_summaries.length > 0 ? (
                          <div className="grid gap-4 md:grid-cols-2">
                            {data.semester_summaries.map((sem) => (
                              <div key={sem.semester_no} className="rounded-xl border bg-card p-4">
                                <div className="flex items-center justify-between gap-3">
                                  <div className="flex items-center gap-2">
                                    <span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-sm font-bold text-primary">
                                      {sem.semester_no}
                                    </span>
                                    <div className="flex flex-col">
                                      <p className="text-sm font-semibold">Semester {sem.semester_no}</p>
                                      <p className="text-xs text-muted-foreground">
                                        {sem.academic_year ?? "—"}
                                      </p>
                                    </div>
                                  </div>
                                  {sem.semester_result && (
                                    <Badge variant={sem.semester_result.toLowerCase() === "pass" ? "success" : "warning"}>
                                      {sem.semester_result}
                                    </Badge>
                                  )}
                                </div>
                                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                                  <div className="flex flex-col">
                                    <span className="text-xs text-muted-foreground">SGPA</span>
                                    <span className="text-base font-semibold tabular-nums">{fmt(sem.semester_sgpa, 2)}</span>
                                  </div>
                                  <div className="flex flex-col">
                                    <span className="text-xs text-muted-foreground">Percentage</span>
                                    <span className="text-base font-semibold tabular-nums">{fmtPct(sem.semester_percentage)}</span>
                                  </div>
                                  <div className="flex flex-col">
                                    <span className="text-xs text-muted-foreground">Attendance</span>
                                    <span className="text-base font-semibold tabular-nums">{fmtPct(sem.semester_attendance_percentage)}</span>
                                  </div>
                                  <div className="flex flex-col">
                                    <span className="text-xs text-muted-foreground">Credits</span>
                                    <span className="text-base font-semibold tabular-nums">
                                      {sem.credits_earned ?? 0}/{sem.credits_registered ?? 0}
                                    </span>
                                  </div>
                                  <div className="flex flex-col">
                                    <span className="text-xs text-muted-foreground">Backlogs</span>
                                    <span className={cn("text-base font-semibold tabular-nums", (sem.backlog_count ?? 0) > 0 ? "text-destructive" : "")}>
                                      {sem.backlog_count ?? 0}
                                    </span>
                                  </div>
                                  <div className="flex flex-col">
                                    <span className="text-xs text-muted-foreground">Standing</span>
                                    <span className="truncate text-base font-semibold">{sem.academic_standing ?? "—"}</span>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <EmptyState icon={ClipboardList} title="No semester data yet" description="Semester-wise academic history will appear here." />
                        )}
                      </div>

                      <div className="flex flex-col gap-3">
                        <SectionTitle>Credit Progress</SectionTitle>
                        {data.semester_summaries.length > 0 ? (
                          <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
                            <SubjectBarChart
                              data={data.semester_summaries.map((sem) => ({
                                name: `S${sem.semester_no}`,
                                registered: sem.credits_registered ?? 0,
                                earned: sem.credits_earned ?? 0,
                              }))}
                              xKey="name"
                              bars={[
                                { dataKey: "registered", name: "Registered", color: "var(--chart-1)" },
                                { dataKey: "earned", name: "Earned", color: "var(--chart-2)" },
                              ]}
                              height={240}
                            />
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="attendance" className="mt-0">
                    <div className="flex flex-col gap-6">
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                        <StatCard
                          label="Overall Attendance"
                          value={fmtPct(s.overall_attendance_percentage)}
                          icon={Percent}
                          tone={attendanceTone(s.overall_attendance_percentage)}
                        />
                        <StatCard
                          label="Subjects Below 75%"
                          value={String(subjectRows.filter((sub) => sub.attendance_percentage != null && sub.attendance_percentage < 75).length)}
                          icon={BookOpen}
                          tone={subjectRows.some((sub) => sub.attendance_percentage != null && sub.attendance_percentage < 75) ? "warning" : "success"}
                        />
                        <StatCard
                          label="Poor Subjects"
                          value={String(poorSubjects.length)}
                          icon={AlertTriangle}
                          tone={poorSubjects.length > 0 ? "destructive" : "success"}
                        />
                      </div>

                      {data.semester_summaries.some((sem) => sem.semester_attendance_percentage != null) && (
                        <div className="flex flex-col gap-3">
                          <SectionTitle>Attendance Trend</SectionTitle>
                          <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
                            <TrendChart
                              data={data.semester_summaries.map((sem) => ({
                                sem: `S${sem.semester_no}`,
                                attendance: sem.semester_attendance_percentage ?? 0,
                              }))}
                              xKey="sem"
                              series={[{ key: "attendance", label: "Attendance", color: "var(--chart-2)" }]}
                              yDomain={[0, 100]}
                              yTickSuffix="%"
                              referenceLines={[{ y: 75, label: "Minimum 75%" }]}
                            />
                          </div>
                        </div>
                      )}

                      {subjectRows.length > 0 && (
                        <div className="flex flex-col gap-3">
                          <SectionTitle>Subject-wise Attendance</SectionTitle>
                          <div className="rounded-xl border bg-card">
                            <Table>
                              <TableHeader>
                                <TableRow>
                                  <TableHead>Subject</TableHead>
                                  <TableHead>Classes</TableHead>
                                  <TableHead className="text-right">Attendance</TableHead>
                                  <TableHead>Status</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {subjectRows.map((sub) => {
                                  const below = sub.attendance_percentage != null && sub.attendance_percentage < 75
                                  return (
                                    <TableRow key={`${sub.subject_id}-${sub.semester_no}-${sub.academic_year}`}>
                                      <TableCell>
                                        <div className="flex flex-col">
                                          <span className="text-sm font-medium">{sub.subject_name}</span>
                                          <span className="text-xs text-muted-foreground">{sub.subject_code}</span>
                                        </div>
                                      </TableCell>
                                      <TableCell className="tabular-nums">
                                        {sub.attended_classes != null ? `${sub.attended_classes}/${sub.total_classes ?? "—"}` : "—"}
                                      </TableCell>
                                      <TableCell className={cn("text-right font-medium tabular-nums", below ? "text-destructive" : "")}>
                                        {fmtPct(sub.attendance_percentage)}
                                      </TableCell>
                                      <TableCell>
                                        <Badge variant={below ? "destructive" : "success"}>
                                          {below ? "Shortage" : "Regular"}
                                        </Badge>
                                      </TableCell>
                                    </TableRow>
                                  )
                                })}
                              </TableBody>
                            </Table>
                          </div>
                        </div>
                      )}
                    </div>
                  </TabsContent>

                  <TabsContent value="performance" className="mt-0">
                    <div className="flex flex-col gap-6">
                      <div className="grid gap-6 lg:grid-cols-2">
                        {data.semester_summaries.some((sem) => sem.semester_sgpa != null) && (
                          <div className="flex flex-col gap-3">
                            <SectionTitle>SGPA Trend</SectionTitle>
                            <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
                              <TrendChart
                                data={data.semester_summaries.map((sem) => ({
                                  sem: `S${sem.semester_no}`,
                                  sgpa: sem.semester_sgpa ?? 0,
                                }))}
                                xKey="sem"
                                series={[{ key: "sgpa", label: "SGPA", color: "var(--chart-1)" }]}
                                yDomain={[0, 10]}
                              />
                            </div>
                          </div>
                        )}
                        {data.semester_summaries.some((sem) => sem.semester_percentage != null) && (
                          <div className="flex flex-col gap-3">
                            <SectionTitle>Semester Performance</SectionTitle>
                            <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
                              <TrendChart
                                data={data.semester_summaries.map((sem) => ({
                                  sem: `S${sem.semester_no}`,
                                  performance: sem.semester_percentage ?? 0,
                                }))}
                                xKey="sem"
                                series={[{ key: "performance", label: "Percentage", color: "var(--chart-3)" }]}
                                yDomain={[0, 100]}
                                yTickSuffix="%"
                              />
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="flex flex-col gap-3">
                        <SectionTitle>Subject-wise Performance</SectionTitle>
                        {data.subject_performance.length > 0 ? (
                          <div className="rounded-xl border bg-card">
                            <Table>
                              <TableHeader>
                                <TableRow>
                                  <TableHead>Subject</TableHead>
                                  <TableHead>Type</TableHead>
                                  <TableHead>Faculty</TableHead>
                                  <TableHead className="text-right">Int / Mid / Ext</TableHead>
                                  <TableHead className="text-right">Total</TableHead>
                                  <TableHead className="text-right">%</TableHead>
                                  <TableHead>Grade</TableHead>
                                  <TableHead>Result</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {data.subject_performance.map((sub) => {
                                  const poor = isPoorSubject(sub)
                                  return (
                                    <TableRow key={`${sub.subject_id}-${sub.semester_no}-${sub.academic_year}`} className={cn(poor && "bg-destructive/5 hover:bg-destructive/10")}>
                                      <TableCell>
                                        <div className="flex flex-col">
                                          <span className="text-sm font-medium">{sub.subject_name}</span>
                                          <span className="text-xs text-muted-foreground">
                                            {sub.subject_code} {sub.semester_no ? `• Sem ${sub.semester_no}` : ""}
                                          </span>
                                        </div>
                                      </TableCell>
                                      <TableCell>
                                        {sub.subject_type ? <Badge variant="secondary">{sub.subject_type}</Badge> : "—"}
                                      </TableCell>
                                      <TableCell className="text-xs text-muted-foreground">{sub.faculty_name ?? "—"}</TableCell>
                                      <TableCell className="text-right tabular-nums">
                                        {sub.internal_marks != null || sub.mid_sem_marks != null || sub.external_marks != null
                                          ? `${fmt(sub.internal_marks, 0)} / ${fmt(sub.mid_sem_marks, 0)} / ${fmt(sub.external_marks, 0)}`
                                          : "—"}
                                      </TableCell>
                                      <TableCell className="text-right font-medium tabular-nums">{fmt(sub.total_marks, 0)}</TableCell>
                                      <TableCell className={cn("text-right font-medium tabular-nums", poor ? "text-destructive" : "")}>
                                        {fmtPct(sub.percentage)}
                                      </TableCell>
                                      <TableCell>
                                        <Badge variant={subjectBadgeVariant[subjectTone(sub)]}>{sub.grade || "—"}</Badge>
                                      </TableCell>
                                      <TableCell>
                                        <span className={cn("text-sm", poor ? "font-medium text-destructive" : "")}>
                                          {sub.result_status ?? "—"}
                                        </span>
                                      </TableCell>
                                    </TableRow>
                                  )
                                })}
                              </TableBody>
                            </Table>
                          </div>
                        ) : (
                          <EmptyState icon={ClipboardList} title="No subject performance data yet" description="Subject-wise marks will appear here once recorded." />
                        )}
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="skills" className="mt-0">
                    <EmptyState
                      icon={Sparkles}
                      title="No skills & activities recorded"
                      description="Projects, certificates, internships, hackathons, skills and achievements will appear here once recorded."
                    />
                  </TabsContent>

                  <TabsContent value="placement" className="mt-0">
                    <div className="flex flex-col gap-6">
                      {data.career ? (
                        <div className="flex flex-col gap-3">
                          <SectionTitle>Career Preferences</SectionTitle>
                          <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
                            <InfoGrid
                              items={[
                                { label: "Preferred Domain", value: data.career.preferred_domain },
                                { label: "Dream Job Role", value: data.career.dream_job_role },
                                { label: "Preferred Industry", value: data.career.preferred_industry },
                                { label: "Work Mode", value: data.career.preferred_work_mode },
                                { label: "Target Package", value: data.career.target_package_lpa != null ? `${data.career.target_package_lpa} LPA` : null },
                                { label: "Higher Studies", value: data.career.higher_studies_interest },
                                { label: "Entrepreneurship", value: data.career.entrepreneurship_interest },
                                { label: "Certification", value: data.career.certification_interest },
                                { label: "Internship Completed", value: data.career.internship_completed },
                              ]}
                            />
                            <div className="mt-4 flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">Readiness Level</span>
                              {data.career.placement_readiness_level ? (
                                <Badge variant="outline">{data.career.placement_readiness_level}</Badge>
                              ) : (
                                <Badge variant="muted">Not assessed</Badge>
                              )}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <EmptyState
                          icon={Target}
                          title="Career preferences not recorded yet"
                          description="Domain interests, job roles and placement preferences will appear here once the student completes their career assessment."
                        />
                      )}

                      <div className="flex flex-col gap-3">
                        <SectionTitle>Placement Readiness</SectionTitle>
                        <EmptyState
                          icon={ShieldCheck}
                          title="Readiness assessment not yet available"
                          description="Technical, communication and problem-solving scores along with resume and interview readiness will appear here once assessed."
                        />
                      </div>
                    </div>
                  </TabsContent>
                </div>
              </Tabs>

              <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t bg-muted/30 px-6 py-3">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!s.email}
                  onClick={() => {
                    window.location.href = `mailto:${s.email}`
                  }}
                >
                  <MessageSquare /> Message
                </Button>
                <Button variant="outline" size="sm" disabled title="Coming soon">
                  <CalendarClock /> Schedule Meeting
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => downloadProfileCsv(data)}
                >
                  <Download /> Report
                </Button>
                <Button variant="outline" size="sm" onClick={() => window.print()}>
                  <Printer /> Print
                </Button>
                <Button variant="secondary" size="sm" onClick={() => handleTabChange("academics")}>
                  <BookOpen /> Full Record
                </Button>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  )
}
