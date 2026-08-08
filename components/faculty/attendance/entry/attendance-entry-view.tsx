"use client"

import * as React from "react"
import Link from "next/link"
import {
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  Clock,
  LoaderCircle,
  RefreshCw,
  Save,
  TriangleAlert,
  Users,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import {
  Select,
  SelectContent,
  SelectIcon,
  SelectItem,
  SelectList,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { EmptyState } from "@/components/shared/state/empty-state"
import { ErrorState } from "@/components/shared/state/error-state"
import type {
  AttendanceEntryMeta,
  AttendanceSession,
  FacultyClassCard,
  LectureAttendance,
  LectureAttendanceSaveRequest,
  LectureAttendanceSaveResponse,
} from "@/lib/faculty-api"

import { AttendanceChangeHistory } from "./attendance-change-history"

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

function todayString(): string {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
}

function weekdayOf(date: string): string {
  return WEEKDAYS[new Date(`${date}T00:00:00`).getDay()]
}

function formatTime(value: string): string {
  if (!value) return ""
  const [hours, minutes] = value.split(":")
  if (hours === undefined || minutes === undefined) return value
  return `${hours}:${minutes}`
}

function sessionLabel(session: AttendanceSession): string {
  const type = session.lecture_type ? ` · ${session.lecture_type}` : ""
  return `Slot ${session.slot_no} · ${formatTime(session.start_time)}–${formatTime(
    session.end_time,
  )}${type}`
}

export function AttendanceEntryView({
  subjectOptions,
  initialSubjectId,
  initialSemester,
  initialAcademicYear,
}: {
  subjectOptions: FacultyClassCard[]
  initialSubjectId?: string
  initialSemester?: number
  initialAcademicYear?: string
}) {
  const [semester] = React.useState<number | undefined>(initialSemester)
  const [academicYear] = React.useState<string | undefined>(initialAcademicYear)

  const defaultSubjectId = React.useMemo(() => {
    if (!initialSubjectId || !subjectOptions.some((o) => o.subject_id === initialSubjectId)) {
      return subjectOptions[0]?.subject_id ?? null
    }
    return initialSubjectId
  }, [initialSubjectId, subjectOptions])

  const [subjectId, setSubjectId] = React.useState<string | null>(defaultSubjectId)
  const [meta, setMeta] = React.useState<AttendanceEntryMeta | null>(null)
  const [metaLoading, setMetaLoading] = React.useState(Boolean(defaultSubjectId))
  const [metaError, setMetaError] = React.useState<string | null>(null)
  const [date, setDate] = React.useState(todayString())
  const [slotNo, setSlotNo] = React.useState<number | null>(null)
  const [lecture, setLecture] = React.useState<LectureAttendance | null>(null)
  const [lectureLoading, setLectureLoading] = React.useState(false)
  const [lectureError, setLectureError] = React.useState<string | null>(null)
  const [statuses, setStatuses] = React.useState<Record<string, "P" | "A">>({})
  const [bulkText, setBulkText] = React.useState("")
  const [bulkAccepted, setBulkAccepted] = React.useState<string[]>([])
  const [bulkRejected, setBulkRejected] = React.useState<string[]>([])
  const [saving, setSaving] = React.useState(false)
  const [saveError, setSaveError] = React.useState<string | null>(null)
  const [saveResult, setSaveResult] = React.useState<LectureAttendanceSaveResponse | null>(null)
  const [activeTab, setActiveTab] = React.useState("entry")

  const queryParams = React.useMemo(() => {
    const params = new URLSearchParams()
    if (semester !== undefined) params.set("semester", String(semester))
    if (academicYear) params.set("academic_year", academicYear)
    return params.toString()
  }, [semester, academicYear])

  const loadMeta = React.useCallback(async () => {
    if (!subjectId) return
    try {
      const qs = queryParams ? `?${queryParams}` : ""
      const res = await fetch(`/api/faculty/subjects/${subjectId}/attendance${qs}`, {
        cache: "no-store",
      })
      const result = (await res.json()) as
        | { ok: true; data: AttendanceEntryMeta }
        | { ok: false; error: { status: number; message: string } }
      if (!result.ok) {
        setMetaError(result.error.message)
        return
      }
      setMeta(result.data)
      if (result.data.sessions.length === 1) {
        setSlotNo(result.data.sessions[0].slot_no)
      }
    } catch {
      setMetaError("Could not load the lecture schedule. Please try again.")
    } finally {
      setMetaLoading(false)
    }
  }, [subjectId, queryParams])

  const loadLecture = React.useCallback(async () => {
    if (!subjectId || !date || slotNo === null) return
    try {
      const params = new URLSearchParams({ slot_no: String(slotNo) })
      if (queryParams) {
        for (const [key, value] of new URLSearchParams(queryParams).entries()) {
          params.set(key, value)
        }
      }
      const res = await fetch(
        `/api/faculty/subjects/${subjectId}/attendance/lectures/${date}?${params.toString()}`,
        { cache: "no-store" },
      )
      const result = (await res.json()) as
        | { ok: true; data: LectureAttendance }
        | { ok: false; error: { status: number; message: string } }
      if (!result.ok) {
        setLectureError(result.error.message)
        return
      }
      setLecture(result.data)
      const next: Record<string, "P" | "A"> = {}
      for (const student of result.data.students) {
        next[student.student_id] = student.attendance_status === "P" ? "P" : "A"
      }
      setStatuses(next)
      setBulkAccepted([])
      setBulkRejected([])
      setSaveResult(null)
    } catch {
      setLectureError("Could not load the lecture attendance. Please try again.")
    } finally {
      setLectureLoading(false)
    }
  }, [subjectId, date, slotNo, queryParams])

  function changeSubject(id: string) {
    setSubjectId(id)
    setMetaLoading(true)
    setMetaError(null)
    setLectureLoading(true)
    setLectureError(null)
    setSlotNo(null)
    setLecture(null)
    setStatuses({})
    setBulkText("")
    setBulkAccepted([])
    setBulkRejected([])
    setSaveResult(null)
  }

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadMeta()
  }, [loadMeta])

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadLecture()
  }, [loadLecture])

  const weekday = date ? weekdayOf(date) : null
  const sessionsForDate = React.useMemo(() => {
    if (!meta || !weekday) return []
    return meta.sessions.filter(
      (s) => s.day_name.toLowerCase() === weekday.toLowerCase(),
    )
  }, [meta, weekday])

  function toggleStatus(studentId: string) {
    setStatuses((prev) => ({
      ...prev,
      [studentId]: prev[studentId] === "P" ? "A" : "P",
    }))
  }

  function markAll(value: "P" | "A") {
    if (!lecture) return
    const next: Record<string, "P" | "A"> = {}
    for (const student of lecture.students) next[student.student_id] = value
    setStatuses(next)
  }

  function applyBulk() {
    if (!lecture) return
    const tokens = bulkText.trim().split(/\s+/).filter(Boolean)
    const accepted: string[] = []
    const rejected: string[] = []
    const presentIds = new Set<string>()
    for (const token of tokens) {
      const num = Number(token)
      if (!Number.isInteger(num) || num < 0) {
        rejected.push(token)
        continue
      }
      const matches = lecture.students.filter(
        (s) => s.enrollment_no === num || s.enrollment_no % 1000 === num,
      )
      if (matches.length === 1) {
        presentIds.add(matches[0].student_id)
        accepted.push(token)
      } else {
        rejected.push(token)
      }
    }
    setBulkAccepted(accepted)
    setBulkRejected(rejected)
    setStatuses((prev) => {
      const next: Record<string, "P" | "A"> = { ...prev }
      for (const student of lecture.students) {
        next[student.student_id] = presentIds.has(student.student_id) ? "P" : "A"
      }
      return next
    })
  }

  async function handleSave() {
    if (!lecture || !subjectId || !date || slotNo === null) return
    const students = lecture.students.map((student) => ({
      student_id: student.student_id,
      attendance_status: statuses[student.student_id] ?? "A",
    }))
    const payload: LectureAttendanceSaveRequest = {
      semester_no: lecture.semester_no,
      academic_year: lecture.academic_year,
      lecture_date: date,
      slot_no: slotNo,
      students,
    }
    setSaving(true)
    setSaveError(null)
    setSaveResult(null)
    try {
      const url = lecture.recorded
        ? `/api/faculty/subjects/${subjectId}/attendance/lectures/${date}?slot_no=${slotNo}`
        : `/api/faculty/subjects/${subjectId}/attendance`
      const res = await fetch(url, {
        method: lecture.recorded ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        cache: "no-store",
      })
      const result = (await res.json()) as
        | { ok: true; data: LectureAttendanceSaveResponse }
        | { ok: false; error: { status: number; message: string } }
      if (!result.ok) {
        setSaveError(result.error.message)
        return
      }
      setSaveResult(result.data)
      await loadLecture()
    } catch {
      setSaveError("Could not save attendance. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  const presentCount = Object.values(statuses).filter((s) => s === "P").length
  const studentCount = lecture?.students.length ?? 0

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Attendance Entry</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Record or correct lecture attendance for a subject and timetable slot.
            </p>
          </div>
          <Link
            href="/faculty/attendance"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back to Attendance Analytics
          </Link>
        </div>
      </section>

      {subjectOptions.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No subjects available"
          description="You have no subjects with a scheduled lecture this term."
        />
      ) : (
        <>
          <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
            <div className="flex flex-wrap items-end gap-4">
              <div className="flex w-full flex-col gap-1.5 sm:w-auto">
                <Label htmlFor="attendance-subject">Subject</Label>
                <Select
                  id="attendance-subject"
                  value={subjectId ?? ""}
                  onValueChange={(value) => {
                    if (value) changeSubject(value)
                  }}
                >
                  <SelectTrigger className="w-full sm:w-80">
                    <SelectValue>
                      {(selected: string | null) => {
                        const option = subjectOptions.find((o) => o.subject_id === selected)
                        return option ? `${option.subject_code} · ${option.subject_name}` : ""
                      }}
                    </SelectValue>
                    <SelectIcon />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectList>
                      {subjectOptions.map((option) => (
                        <SelectItem key={option.subject_id} value={option.subject_id}>
                          {option.subject_code} · {option.subject_name}
                        </SelectItem>
                      ))}
                    </SelectList>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex w-full flex-col gap-1.5 sm:w-auto">
                <Label htmlFor="attendance-date">Lecture date</Label>
                <Input
                  id="attendance-date"
                  type="date"
                  value={date}
                  onChange={(event) => {
                    const nextDate = event.target.value
                    setDate(nextDate)
                    setLecture(null)
                    setLectureLoading(true)
                    setLectureError(null)
                    const nextWeekday = nextDate ? weekdayOf(nextDate) : null
                    const matches =
                      nextWeekday && meta
                        ? meta.sessions.filter(
                            (s) => s.day_name.toLowerCase() === nextWeekday.toLowerCase(),
                          )
                        : []
                    setSlotNo(matches.length === 1 ? matches[0].slot_no : null)
                  }}
                  className="w-full sm:w-44"
                />
              </div>
              <div className="flex w-full flex-col gap-1.5 sm:w-auto">
                <Label htmlFor="attendance-slot">Slot</Label>
                <Select
                  id="attendance-slot"
                  value={slotNo === null ? "" : String(slotNo)}
                  onValueChange={(value) => {
                    if (value) {
                      setSlotNo(Number(value))
                      setLectureLoading(true)
                      setLectureError(null)
                    }
                  }}
                >
                  <SelectTrigger className="w-full sm:w-64">
                    <SelectValue>
                      {(selected: string | null) => {
                        const session = sessionsForDate.find(
                          (s) => String(s.slot_no) === selected,
                        )
                        return session ? sessionLabel(session) : ""
                      }}
                    </SelectValue>
                    <SelectIcon />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectList>
                      {sessionsForDate.map((session) => (
                        <SelectItem key={session.slot_no} value={String(session.slot_no)}>
                          {sessionLabel(session)}
                        </SelectItem>
                      ))}
                    </SelectList>
                  </SelectContent>
                </Select>
              </div>
            </div>
            {meta && (
              <p className="mt-3 text-xs text-muted-foreground">
                {meta.subject_code} · {meta.subject_name} · Sem {meta.semester_no} ·{" "}
                {meta.academic_year} · {meta.sessions.length} scheduled session
                {meta.sessions.length === 1 ? "" : "s"}
              </p>
            )}
          </section>

          {metaLoading && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <LoaderCircle className="size-4 animate-spin" />
              Loading lecture schedule…
            </p>
          )}
          {metaError && <ErrorState title="Failed to load lecture schedule" description={metaError} />}

          {meta && meta.sessions.length === 0 && !metaLoading && (
            <EmptyState
              icon={CalendarDays}
              title="No scheduled sessions"
              description="There is no timetable session for this subject in the selected term."
            />
          )}

          {meta && meta.sessions.length > 0 && (
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList>
                <TabsTrigger value="entry">Attendance grid</TabsTrigger>
                <TabsTrigger value="history">Change history</TabsTrigger>
              </TabsList>

              <TabsContent value="entry">
                <div className="flex flex-col gap-4">
                  {lectureLoading && (
                    <p
                      className="flex items-center gap-2 text-sm text-muted-foreground"
                      role="status"
                    >
                      <LoaderCircle className="size-4 animate-spin" />
                      Loading lecture…
                    </p>
                  )}

                  {lectureError && (
                    <ErrorState title="Failed to load lecture" description={lectureError} />
                  )}

                  {lecture && !lectureLoading && (
                    <>
                      {lecture.recorded ? (
                        <section
                          className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4"
                          role="status"
                        >
                          <TriangleAlert className="size-4 shrink-0 text-amber-500" />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium">
                              Lecture already recorded
                              {lecture.lecture_number !== null
                                ? ` (lecture #${lecture.lecture_number})`
                                : ""}{" "}
                              for {lecture.day_name}, slot {lecture.slot_no}.
                            </p>
                            <p className="text-sm text-muted-foreground">
                              Editing this grid corrects the existing record.
                            </p>
                          </div>
                        </section>
                      ) : (
                        <section className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
                          <CalendarDays className="size-4 shrink-0 text-amber-500" />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium">Not yet recorded</p>
                            <p className="text-sm text-muted-foreground">
                              Saving creates a new lecture record for {lecture.day_name}, slot{" "}
                              {lecture.slot_no}.
                            </p>
                          </div>
                        </section>
                      )}

                      {saveError && (
                        <section
                          className="flex flex-wrap items-center gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4"
                          role="alert"
                        >
                          <TriangleAlert className="size-4 text-destructive" />
                          <p className="text-sm text-destructive">{saveError}</p>
                        </section>
                      )}

                      <section
                        className="rounded-xl bg-card p-4 ring-1 ring-foreground/10"
                        aria-label="Lecture metadata"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-3">
                            <Badge variant="secondary">
                              <Clock className="mr-1 size-3" />
                              Slot {lecture.slot_no}
                            </Badge>
                            <Badge variant="muted">
                              {formatTime(lecture.start_time)}–{formatTime(lecture.end_time)}
                            </Badge>
                            <Badge variant="muted">{lecture.day_name}</Badge>
                            {lecture.lecture_type && (
                              <Badge variant="muted">{lecture.lecture_type}</Badge>
                            )}
                            {lecture.faculty_name && (
                              <Badge variant="muted">{lecture.faculty_name}</Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setLectureLoading(true)
                                setLectureError(null)
                                void loadLecture()
                              }}
                            >
                              <RefreshCw className="size-3.5" />
                              Refresh
                            </Button>
                          </div>
                        </div>
                      </section>

                      <section
                        className="rounded-xl bg-card p-4 ring-1 ring-foreground/10"
                        aria-label="Bulk entry"
                      >
                        <div className="flex flex-col gap-2">
                          <Label htmlFor="bulk-input">Bulk present list</Label>
                          <div className="flex flex-wrap items-center gap-2">
                            <Input
                              id="bulk-input"
                              value={bulkText}
                              onChange={(event) => setBulkText(event.target.value)}
                              placeholder="e.g. 1 2 3 — enrollment suffixes to mark Present"
                              className="h-9 w-full sm:max-w-md"
                            />
                            <Button variant="secondary" onClick={applyBulk} disabled={!bulkText.trim()}>
                              Apply
                            </Button>
                            <Button variant="outline" onClick={() => markAll("P")}>
                              All present
                            </Button>
                            <Button variant="outline" onClick={() => markAll("A")}>
                              All absent
                            </Button>
                          </div>
                          {bulkAccepted.length > 0 && (
                            <p className="text-sm text-chart-2">
                              Marked present: {bulkAccepted.join(", ")}
                            </p>
                          )}
                          {bulkRejected.length > 0 && (
                            <p className="text-sm text-destructive">
                              Rejected (no unique match): {bulkRejected.join(", ")}
                            </p>
                          )}
                        </div>
                      </section>

                      <section className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Enrollment No</TableHead>
                              <TableHead>Student</TableHead>
                              <TableHead className="w-28">Attendance</TableHead>
                              <TableHead>Current</TableHead>
                              <TableHead>Status</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {lecture.students.map((student) => (
                              <TableRow key={student.student_id}>
                                <TableCell className="font-mono text-xs text-muted-foreground">
                                  {String(student.enrollment_no).padStart(3, "0")}
                                </TableCell>
                                <TableCell className="font-medium">
                                  {student.first_name} {student.last_name}
                                </TableCell>
                                <TableCell>
                                  <div className="flex items-center gap-1">
                                    <Button
                                      size="xs"
                                      variant={
                                        statuses[student.student_id] === "P"
                                          ? "default"
                                          : "outline"
                                      }
                                      onClick={() => toggleStatus(student.student_id)}
                                      className={
                                        statuses[student.student_id] === "P"
                                          ? "bg-chart-2 text-white hover:bg-chart-2/80"
                                          : ""
                                      }
                                    >
                                      P
                                    </Button>
                                    <Button
                                      size="xs"
                                      variant={
                                        statuses[student.student_id] === "A"
                                          ? "destructive"
                                          : "outline"
                                      }
                                      onClick={() => toggleStatus(student.student_id)}
                                    >
                                      A
                                    </Button>
                                  </div>
                                </TableCell>
                                <TableCell className="tabular-nums">
                                  {student.attendance_percentage !== null
                                    ? `${student.attendance_percentage.toFixed(1)}%`
                                    : "—"}
                                  {student.shortage_flag === "Yes" && (
                                    <Badge variant="destructive" className="ml-2">
                                      Shortage
                                    </Badge>
                                  )}
                                </TableCell>
                                <TableCell className="text-muted-foreground">
                                  {student.eligibility_status ?? "—"}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </section>

                      <section
                        className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10"
                        aria-label="Save bar"
                      >
                        <div className="flex min-w-0 flex-col gap-1">
                          <p className="text-sm font-medium">
                            {studentCount} students · {presentCount} present ·{" "}
                            {studentCount - presentCount} absent
                          </p>
                          {saveResult ? (
                            <p
                              className="flex flex-wrap items-center gap-1.5 text-sm text-chart-2"
                              role="status"
                            >
                              <CheckCircle2 className="size-4 shrink-0" />
                              Saved · {saveResult.summary.inserted} inserted ·{" "}
                              {saveResult.summary.updated} updated ·{" "}
                              {saveResult.summary.unchanged} unchanged
                              {saveResult.lecture_number !== null &&
                                ` · Lecture #${saveResult.lecture_number}`}
                            </p>
                          ) : (
                            <p className="text-xs text-muted-foreground">
                              Aggregate percentages and shortage flags refresh after save.
                            </p>
                          )}
                        </div>
                        <Button
                          onClick={() => void handleSave()}
                          disabled={saving || studentCount === 0}
                        >
                          {saving ? (
                            <LoaderCircle className="size-4 animate-spin" />
                          ) : (
                            <Save className="size-4" />
                          )}
                          {saving
                            ? "Saving…"
                            : lecture.recorded
                              ? "Save correction"
                              : "Record lecture"}
                        </Button>
                      </section>
                    </>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="history">
                {meta && (
                  <AttendanceChangeHistory
                    subjectId={meta.subject_id}
                    semester={meta.semester_no}
                    academicYear={meta.academic_year}
                  />
                )}
              </TabsContent>
            </Tabs>
          )}
        </>
      )}
    </div>
  )
}
