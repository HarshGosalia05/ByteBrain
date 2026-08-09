"use client"

import * as React from "react"
import {
  CalendarDays,
  Check,
  CheckCheck,
  Eraser,
  History,
  LoaderCircle,
  RefreshCw,
  Save,
  Search,
  TriangleAlert,
  UserX,
  X,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectIcon,
  SelectItem,
  SelectList,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/state/empty-state"
import { ErrorState } from "@/components/shared/state/error-state"
import { AttendanceChangeHistory } from "./attendance-change-history"
import type {
  AttendanceEntryMeta,
  AttendanceSession,
  FacultyClassCard,
  LectureAttendance,
  LectureAttendanceSaveResponse,
} from "@/lib/faculty-api"
import { cn } from "@/lib/utils"

type Status = "P" | "A"
type StatusMap = Record<string, Status>

type SessionTerm = { semester: number; academic_year: string | null }

type Notice = { kind: "success" | "error"; message: string }

type BffError = { status: number; code: string; message: string }
type BffData<T> =
  | { ok: true; data: T; fetchedAt: string }
  | { ok: false; error: BffError }

async function fetchMeta(
  subjectId: string,
  term: SessionTerm | null,
): Promise<BffData<AttendanceEntryMeta>> {
  const params = new URLSearchParams({ refresh: "1" })
  if (term?.semester) params.set("semester", String(term.semester))
  if (term?.academic_year) params.set("academic_year", term.academic_year)
  const res = await fetch(`/api/faculty/subjects/${subjectId}/attendance?${params.toString()}`)
  return (await res.json()) as BffData<AttendanceEntryMeta>
}

async function fetchLecture(
  subjectId: string,
  date: string,
  slot: number,
  term: SessionTerm | null,
): Promise<BffData<LectureAttendance>> {
  const params = new URLSearchParams({ slot_no: String(slot), refresh: "1" })
  if (term?.semester) params.set("semester", String(term.semester))
  if (term?.academic_year) params.set("academic_year", term.academic_year)
  const res = await fetch(
    `/api/faculty/subjects/${subjectId}/attendance/lectures/${date}?${params.toString()}`,
    { cache: "no-store" },
  )
  return (await res.json()) as BffData<LectureAttendance>
}

async function saveLecture(
  subjectId: string,
  payload: {
    semester_no: number
    academic_year: string
    lecture_date: string
    slot_no: number
    students: { student_id: string; attendance_status: "P" | "A" }[]
    allow_correction?: boolean
  },
): Promise<BffData<LectureAttendanceSaveResponse>> {
  const res = await fetch(`/api/faculty/subjects/${subjectId}/attendance/lecture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  return (await res.json()) as BffData<LectureAttendanceSaveResponse>
}

function formatTime(value: string | null | undefined): string {
  if (!value) return ""
  return value.slice(0, 5)
}

function localDateString(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, "0")
  const day = String(value.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function dayNameFromDate(value: string): string {
  const parsed = new Date(`${value}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return ""
  return parsed.toLocaleDateString("en-US", { weekday: "long" })
}

function slotLabel(session: AttendanceSession): string {
  const start = formatTime(session.start_time)
  const end = formatTime(session.end_time)
  const time = start && end ? `${start} – ${end}` : start || end
  const type = session.lecture_type ? ` · ${session.lecture_type}` : ""
  return `Slot ${session.slot_no} · ${time}${type}`
}

function statusesFromLecture(lecture: LectureAttendance): StatusMap {
  const map: StatusMap = {}
  for (const row of lecture.students) {
    if (row.attendance_status === "P" || row.attendance_status === "A") {
      map[row.student_id] = row.attendance_status
    }
  }
  return map
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
  const [subjectId, setSubjectId] = React.useState<string | null>(initialSubjectId ?? null)
  const [sessionTerm, setSessionTerm] = React.useState<SessionTerm | null>(
    initialSemester !== undefined && initialAcademicYear
      ? { semester: initialSemester, academic_year: initialAcademicYear }
      : null,
  )
  const [date, setDate] = React.useState(() => localDateString(new Date()))
  const [slotNo, setSlotNo] = React.useState<number | null>(null)

  const [meta, setMeta] = React.useState<AttendanceEntryMeta | null>(null)
  const [metaLoading, setMetaLoading] = React.useState(false)
  const [metaError, setMetaError] = React.useState<number | null>(null)
  const [metaReloadKey, setMetaReloadKey] = React.useState(0)
  const [resolvedTerm, setResolvedTerm] = React.useState<SessionTerm | null>(null)

  const [lecture, setLecture] = React.useState<LectureAttendance | null>(null)
  const [lectureLoading, setLectureLoading] = React.useState(false)
  const [lectureError, setLectureError] = React.useState<number | null>(null)

  const [statuses, setStatuses] = React.useState<StatusMap>({})
  const [search, setSearch] = React.useState("")
  const [saving, setSaving] = React.useState(false)
  const [showIncomplete, setShowIncomplete] = React.useState(false)
  const [confirmIncomplete, setConfirmIncomplete] = React.useState(false)
  const [notice, setNotice] = React.useState<Notice | null>(null)

  const semesterOptions = React.useMemo(
    () => Array.from(new Set(subjectOptions.map((s) => s.semester_no))).sort((a, b) => a - b),
    [subjectOptions],
  )

  const sessionsForDate = React.useMemo(() => {
    if (!meta) return []
    const day = dayNameFromDate(date)
    if (!day) return []
    return meta.sessions.filter((session) => session.day_name === day)
  }, [meta, date])

  const query = search.trim().toLowerCase()
  const visibleStudents = React.useMemo(() => {
    if (!lecture) return []
    if (!query) return lecture.students
    return lecture.students.filter((student) => {
      const name = `${student.first_name} ${student.last_name}`.toLowerCase()
      return (
        name.includes(query) ||
        String(student.enrollment_no).includes(query) ||
        student.student_id.toLowerCase().includes(query)
      )
    })
  }, [lecture, query])

  const totalStudents = lecture?.students.length ?? 0
  const presentCount = Object.values(statuses).filter((s) => s === "P").length
  const absentCount = Object.values(statuses).filter((s) => s === "A").length
  const notMarkedCount = Math.max(0, totalStudents - presentCount - absentCount)

  function resetSession() {
    setLecture(null)
    setLectureError(null)
    setStatuses({})
    setSlotNo(null)
    setNotice(null)
    setShowIncomplete(false)
    setConfirmIncomplete(false)
  }

  function changeSubject(nextId: string | null) {
    setSubjectId(nextId)
    resetSession()
  }

  function changeTerm(term: { semester: number } | null) {
    setSessionTerm(term ? { semester: term.semester, academic_year: null } : null)
    resetSession()
  }

  function changeDate(nextDate: string) {
    setDate(nextDate)
    resetSession()
  }

  function changeSlot(nextSlot: number | null) {
    setSlotNo(nextSlot)
    setLecture(null)
    setLectureError(null)
    setStatuses({})
    setNotice(null)
    setShowIncomplete(false)
    setConfirmIncomplete(false)
  }

  // Auto-select the only session of the day, if unambiguous.
  React.useEffect(() => {
    if (sessionsForDate.length === 1 && slotNo === null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSlotNo(sessionsForDate[0].slot_no)
    }
  }, [sessionsForDate, slotNo])

  // Load the entry meta (schedule + class list) whenever the subject or term changes.
  React.useEffect(() => {
    let cancelled = false
    async function run() {
      if (!subjectId) {
        setMeta(null)
        setMetaLoading(false)
        setMetaError(null)
        return
      }
      setMetaLoading(true)
      setMetaError(null)
      const result = await fetchMeta(subjectId, sessionTerm)
      if (cancelled) return
      if (result.ok) {
        setMeta(result.data)
        setResolvedTerm({
          semester: result.data.semester_no,
          academic_year: result.data.academic_year,
        })
      } else {
        setMeta(null)
        setResolvedTerm(null)
        setMetaError(result.error.status)
      }
      setMetaLoading(false)
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [subjectId, sessionTerm, metaReloadKey])

  // Load the lecture attendance whenever the session selection is complete.
  React.useEffect(() => {
    let cancelled = false
    async function run() {
      if (!subjectId || !date || slotNo === null || !resolvedTerm) {
        setLecture(null)
        setLectureError(null)
        return
      }
      setLectureLoading(true)
      setLectureError(null)
      const result = await fetchLecture(subjectId, date, slotNo, resolvedTerm)
      if (cancelled) return
      setLectureLoading(false)
      if (result.ok) {
        setLecture(result.data)
        setStatuses(statusesFromLecture(result.data))
      } else {
        setLecture(null)
        setStatuses({})
        setLectureError(result.error.status)
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [subjectId, date, slotNo, resolvedTerm])

  // Auto-dismiss success/error notices.
  React.useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(
      () => setNotice(null),
      notice.kind === "success" ? 4000 : 6000,
    )
    return () => window.clearTimeout(timer)
  }, [notice])

  function pressStatus(studentId: string, status: Status) {
    setStatuses((prev) => {
      const next = { ...prev }
      if (prev[studentId] === status) {
        delete next[studentId]
      } else {
        next[studentId] = status
      }
      return next
    })
  }

  function clearStatus(studentId: string) {
    setStatuses((prev) => {
      const next = { ...prev }
      delete next[studentId]
      return next
    })
  }

  function markAll(status: Status) {
    if (!lecture) return
    const next: StatusMap = {}
    for (const student of lecture.students) {
      next[student.student_id] = status
    }
    setStatuses(next)
  }

  async function refreshLecture(silent = false) {
    if (!subjectId || !date || slotNo === null || !resolvedTerm) return
    if (!silent) setLectureLoading(true)
    setLectureError(null)
    const result = await fetchLecture(subjectId, date, slotNo, resolvedTerm)
    if (!silent) setLectureLoading(false)
    if (result.ok) {
      setLecture(result.data)
      setStatuses(statusesFromLecture(result.data))
    } else {
      setLecture(null)
      setLectureError(result.error.status)
    }
  }

  async function persist() {
    if (!subjectId || !lecture || !resolvedTerm) return
    setSaving(true)
    setNotice(null)
    const students = lecture.students
      .filter((student) => statuses[student.student_id])
      .map((student) => ({
        student_id: student.student_id,
        attendance_status: statuses[student.student_id],
      }))
    const result = await saveLecture(subjectId, {
      semester_no: resolvedTerm.semester,
      academic_year: resolvedTerm.academic_year ?? "",
      lecture_date: lecture.lecture_date,
      slot_no: lecture.slot_no,
      students,
      allow_correction: true,
    })
    setSaving(false)
    if (result.ok) {
      setShowIncomplete(false)
      setConfirmIncomplete(false)
      setNotice({
        kind: "success",
        message: `Attendance saved for ${result.data.lecture_date} · Slot ${result.data.slot_no}.`,
      })
      void refreshLecture(true)
    } else {
      setNotice({ kind: "error", message: result.error.message })
    }
  }

  function handleSaveClick() {
    if (!lecture) return
    const unmarked = lecture.students.filter((student) => !statuses[student.student_id])
    if (unmarked.length > 0 && !confirmIncomplete) {
      setShowIncomplete(true)
      return
    }
    setShowIncomplete(false)
    void persist()
  }

  const metaDescription =
    metaError === 404
      ? "No active teaching term or lecture schedule could be found for this subject."
      : "Unable to load the lecture schedule. Please try again."

  const lectureDescription =
    lectureError === 404
      ? "No valid lecture session was found for the selected date and slot."
      : "Unable to load the lecture attendance. Please try again."

  const slotPlaceholder = (): string => {
    if (!subjectId) return "Select subject"
    if (metaLoading) return "Loading slots…"
    if (metaError) return "Unable to load slots"
    if (!meta) return "Select slot"
    if (sessionsForDate.length === 0) return "No slots available"
    return "Select slot"
  }

  const noLectureDescription =
    meta && meta.sessions.length > 0
      ? `No attendance session is available on ${dayNameFromDate(date)}. This subject's weekly sessions are on ${Array.from(
          new Set(meta.sessions.map((s) => s.day_name)),
        ).join(", ")}.`
      : "No attendance session is available for this subject on the selected date."

  const termChip =
    "flex min-h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
  const termChipActive = "border-primary bg-primary text-primary-foreground"
  const termChipIdle = "border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground"

  return (
    <div className="flex flex-col gap-4">
      <section className="flex flex-col gap-4 rounded-xl border bg-card p-4 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="entry-subject" className="text-xs font-medium text-muted-foreground">
              Subject
            </label>
            <Select value={subjectId ?? null} onValueChange={(value) => changeSubject(value)}>
              <SelectTrigger id="entry-subject" className="w-full">
                <SelectValue>
                  {(selected: string | null) =>
                    selected
                      ? subjectOptions.find((s) => s.subject_id === selected)?.subject_name ??
                        selected
                      : "Select subject"
                  }
                </SelectValue>
                <SelectIcon />
              </SelectTrigger>
              <SelectContent>
                <SelectList>
                  {subjectOptions.map((subject) => (
                    <SelectItem key={subject.subject_id} value={subject.subject_id}>
                      {subject.subject_code} · {subject.subject_name}
                    </SelectItem>
                  ))}
                </SelectList>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">Semester</span>
            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by semester">
              <button
                type="button"
                onClick={() => changeTerm(null)}
                aria-pressed={!sessionTerm}
                className={cn(termChip, !sessionTerm ? termChipActive : termChipIdle)}
              >
                Auto
              </button>
              {semesterOptions.map((semester) => (
                <button
                  key={semester}
                  type="button"
                  onClick={() => changeTerm({ semester })}
                  aria-pressed={sessionTerm?.semester === semester}
                  className={cn(termChip, sessionTerm?.semester === semester ? termChipActive : termChipIdle)}
                >
                  Sem {semester}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="entry-date" className="text-xs font-medium text-muted-foreground">
              Lecture date
            </label>
            <Input
              id="entry-date"
              type="date"
              value={date}
              max={localDateString(new Date())}
              onChange={(event) => changeDate(event.target.value)}
              className="h-9"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="entry-slot" className="text-xs font-medium text-muted-foreground">
              Slot
            </label>
            <Select
              value={slotNo !== null ? String(slotNo) : null}
              onValueChange={(value) => changeSlot(value !== null ? Number(value) : null)}
              disabled={!subjectId || sessionsForDate.length === 0}
            >
              <SelectTrigger id="entry-slot" className="w-full">
                <SelectValue>
                  {(selected: string | null) => {
                    if (selected) {
                      const session = sessionsForDate.find((s) => String(s.slot_no) === selected)
                      return session ? slotLabel(session) : `Slot ${selected}`
                    }
                    if (sessionsForDate.length === 1 && slotNo === null) {
                      return slotLabel(sessionsForDate[0])
                    }
                    return slotPlaceholder()
                  }}
                </SelectValue>
                <SelectIcon />
              </SelectTrigger>
              <SelectContent>
                <SelectList>
                  {sessionsForDate.map((session) => (
                    <SelectItem key={session.slot_no} value={String(session.slot_no)}>
                      {slotLabel(session)}
                    </SelectItem>
                  ))}
                </SelectList>
              </SelectContent>
            </Select>
          </div>
        </div>

        {meta && (
          <div className="flex flex-wrap items-center gap-2 border-t pt-3 text-sm">
            <Badge variant="outline">{meta.subject_code}</Badge>
            <span className="font-medium">{meta.subject_name}</span>
            <span className="text-muted-foreground">
              Semester {meta.semester_no} · {meta.academic_year}
            </span>
            <span className="text-muted-foreground">·</span>
            <span className="text-muted-foreground">{meta.students.length} enrolled</span>
            <span className="text-muted-foreground">·</span>
            <span className="text-muted-foreground">{meta.sessions.length} weekly sessions</span>
          </div>
        )}
      </section>

      {notice && (
        <div
          role="status"
          className={cn(
            "flex items-start gap-3 rounded-xl border px-4 py-3",
            notice.kind === "success"
              ? "border-chart-2/40 bg-chart-2/10"
              : "border-destructive/40 bg-destructive/10",
          )}
        >
          {notice.kind === "success" ? (
            <Check className="mt-0.5 size-4 shrink-0 text-chart-2" />
          ) : (
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-destructive" />
          )}
          <p className="flex-1 text-sm">{notice.message}</p>
          <button
            type="button"
            onClick={() => setNotice(null)}
            aria-label="Dismiss"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>
      )}

      <Tabs defaultValue="entry">
        <TabsList>
          <TabsTrigger value="entry">Daily entry</TabsTrigger>
          <TabsTrigger value="history">Change history</TabsTrigger>
        </TabsList>

        <TabsContent value="entry">
          {!subjectId ? (
            <EmptyState
              icon={CalendarDays}
              title="Select a subject to begin"
              description="Pick a subject and a lecture date to record attendance."
            />
          ) : metaLoading ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <LoaderCircle className="size-4 animate-spin" />
              Loading lecture schedule…
            </p>
          ) : metaError ? (
            <ErrorState
              title="Unable to load lecture schedule"
              description={metaDescription}
              onRetry={() => setMetaReloadKey((key) => key + 1)}
            />
          ) : !meta ? null : sessionsForDate.length === 0 ? (
            <EmptyState
              icon={CalendarDays}
              title="No lecture scheduled"
              description={noLectureDescription}
            />
          ) : slotNo === null ? (
            <EmptyState
              icon={CalendarDays}
              title="Select a slot"
              description={`${sessionsForDate.length} lecture session${sessionsForDate.length === 1 ? "" : "s"} scheduled for ${dayNameFromDate(date)}. Choose a slot to begin.`}
            />
          ) : lectureLoading ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <LoaderCircle className="size-4 animate-spin" />
              Loading lecture…
            </p>
          ) : lectureError ? (
            <ErrorState
              title="Unable to load lecture"
              description={lectureDescription}
              onRetry={() => void refreshLecture()}
            />
          ) : lecture ? (
            <div className="flex flex-col gap-4">
              <div
                className={cn(
                  "flex flex-wrap items-start gap-3 rounded-xl border px-4 py-3",
                  lecture.recorded
                    ? "border-border bg-muted/50"
                    : "border-chart-3/40 bg-chart-3/10",
                )}
              >
                {lecture.recorded ? (
                  <Check className="mt-0.5 size-4 shrink-0 text-chart-2" />
                ) : (
                  <TriangleAlert className="mt-0.5 size-4 shrink-0 text-chart-3" />
                )}
                <div className="flex-1">
                  <p className="text-sm font-medium">
                    {lecture.recorded ? "Recorded lecture" : "Not recorded yet"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {lecture.recorded
                      ? `Lecture ${lecture.lecture_number ?? "—"} is already recorded. Changes below update the existing records.`
                      : "This lecture has not been recorded. Save attendance to record it."}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void refreshLecture()}
                  disabled={saving}
                  title="Reload lecture from server"
                >
                  <RefreshCw className={cn(lectureLoading && "animate-spin")} />
                  Refresh
                </Button>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">Total {totalStudents}</Badge>
                  <Badge variant="success">Present {presentCount}</Badge>
                  <Badge variant="destructive">Absent {absentCount}</Badge>
                  <Badge variant="muted">Not marked {notMarkedCount}</Badge>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative">
                    <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Search students…"
                      aria-label="Search students"
                      className="h-9 w-52 pr-8 pl-8"
                    />
                    {search && (
                      <button
                        type="button"
                        onClick={() => setSearch("")}
                        aria-label="Clear search"
                        className="absolute top-1/2 right-2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                      >
                        <X className="size-4" />
                      </button>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => markAll("P")}
                    disabled={saving}
                    title="Mark all students present"
                  >
                    <CheckCheck />
                    Mark all present
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => markAll("A")}
                    disabled={saving}
                    title="Mark all students absent"
                  >
                    <UserX />
                    Mark all absent
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setStatuses({})}
                    disabled={saving}
                    title="Clear all statuses"
                  >
                    <Eraser />
                    Clear all
                  </Button>
                </div>
              </div>

              {query && (
                <p className="text-xs text-muted-foreground">
                  Showing {visibleStudents.length} of {totalStudents} students
                </p>
              )}

              {visibleStudents.length === 0 ? (
                <EmptyState
                  icon={Search}
                  title="No matching students"
                  description="Try a different search term."
                />
              ) : (
                <div className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-28">Enrollment</TableHead>
                        <TableHead>Student</TableHead>
                        <TableHead className="w-72">Status</TableHead>
                        <TableHead className="w-28 text-right">Attendance %</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {visibleStudents.map((student) => {
                        const status = statuses[student.student_id]
                        return (
                          <TableRow key={student.student_id}>
                            <TableCell className="font-mono text-xs text-muted-foreground">
                              {student.enrollment_no}
                            </TableCell>
                            <TableCell>
                              <p className="font-medium">
                                {student.first_name} {student.last_name}
                              </p>
                              <p className="font-mono text-xs text-muted-foreground">
                                {student.student_id}
                              </p>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1.5">
                                <button
                                  type="button"
                                  onClick={() => pressStatus(student.student_id, "P")}
                                  aria-label={`Mark ${student.first_name} ${student.last_name} present`}
                                  aria-pressed={status === "P"}
                                  title="Present"
                                  className={cn(
                                    "h-7 w-9 rounded-md border text-xs font-semibold transition-colors",
                                    status === "P"
                                      ? "border-transparent bg-chart-2 text-white hover:bg-chart-2/80"
                                      : "border-border bg-background text-muted-foreground hover:bg-muted",
                                  )}
                                >
                                  P
                                </button>
                                <button
                                  type="button"
                                  onClick={() => pressStatus(student.student_id, "A")}
                                  aria-label={`Mark ${student.first_name} ${student.last_name} absent`}
                                  aria-pressed={status === "A"}
                                  title="Absent"
                                  className={cn(
                                    "h-7 w-9 rounded-md border text-xs font-semibold transition-colors",
                                    status === "A"
                                      ? "border-transparent bg-destructive text-white hover:bg-destructive/80"
                                      : "border-border bg-background text-muted-foreground hover:bg-muted",
                                  )}
                                >
                                  A
                                </button>
                                <button
                                  type="button"
                                  onClick={() => clearStatus(student.student_id)}
                                  aria-label={`Clear status for ${student.first_name} ${student.last_name}`}
                                  aria-pressed={!status}
                                  title="Not marked"
                                  className={cn(
                                    "h-7 w-9 rounded-md border text-xs transition-colors",
                                    !status
                                      ? "border-border bg-muted text-muted-foreground"
                                      : "border-border bg-background text-muted-foreground hover:bg-muted",
                                  )}
                                >
                                  —
                                </button>
                              </div>
                            </TableCell>
                            <TableCell className="text-right">
                              {student.attendance_percentage !== null &&
                              student.attendance_percentage !== undefined
                                ? `${student.attendance_percentage.toFixed(1)}%`
                                : "—"}
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}

              {showIncomplete && (
                <div
                  role="alert"
                  className="flex flex-wrap items-center gap-3 rounded-xl border border-chart-3/40 bg-chart-3/10 px-4 py-3"
                >
                  <TriangleAlert className="size-4 shrink-0 text-chart-3" />
                  <div className="min-w-48 flex-1 text-sm">
                    <p className="font-medium">
                      {notMarkedCount} student{notMarkedCount === 1 ? "" : "s"} not marked
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Mark attendance for every student before saving, or save as-is and leave the
                      rest unrecorded.
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => markAll("P")}
                    disabled={saving}
                  >
                    <CheckCheck />
                    Mark all present
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    disabled={saving}
                    onClick={() => {
                      setConfirmIncomplete(true)
                      setShowIncomplete(false)
                      void persist()
                    }}
                  >
                    Save anyway
                  </Button>
                </div>
              )}

              <div className="sticky bottom-3 z-10 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3 shadow-sm">
                <div className="flex items-center gap-2 text-sm">
                  {saving ? (
                    <LoaderCircle className="size-4 animate-spin text-muted-foreground" />
                  ) : (
                    <Check className="size-4 text-chart-2" />
                  )}
                  <span className="font-medium">{saving ? "Saving…" : "Ready to save"}</span>
                  <span className="text-muted-foreground">
                    {presentCount} present · {absentCount} absent · {notMarkedCount} not marked
                  </span>
                </div>
                <Button
                  size="sm"
                  onClick={handleSaveClick}
                  disabled={saving || totalStudents === 0}
                >
                  {saving ? <LoaderCircle className="animate-spin" /> : <Save />}
                  {lecture.recorded ? "Update attendance" : "Save attendance"}
                </Button>
              </div>
            </div>
          ) : null}
        </TabsContent>

        <TabsContent value="history">
          {subjectId ? (
            <AttendanceChangeHistory
              subjectId={subjectId}
              semester={resolvedTerm?.semester}
              academicYear={resolvedTerm?.academic_year ?? undefined}
              lectureDate={date}
              slotNo={slotNo ?? undefined}
            />
          ) : (
            <EmptyState
              icon={History}
              title="Select a subject"
              description="Pick a subject to view its attendance change history."
            />
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
