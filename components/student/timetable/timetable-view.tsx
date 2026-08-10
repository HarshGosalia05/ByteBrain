import Link from "next/link"
import {
  ArrowRight,
  CalendarDays,
  CalendarX2,
  CircleCheck,
  Clock3,
  Coffee,
  Info,
  ListTodo,
  Target,
  TriangleAlert,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/state/empty-state"
import { PageHeader } from "@/components/shared/layout/page-header"
import type {
  DailyAssistantResponse,
  DailyClass,
  StudentTimetableResponse,
  StudentTimetableSession,
  StudyPriority,
} from "@/lib/student-api"
import { cn } from "@/lib/utils"

const DAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const

function formatTime(value: string): string {
  return value.length >= 5 ? value.slice(0, 5) : value
}

function timeRange(start: string, end: string): string {
  return `${formatTime(start)}–${formatTime(end)}`
}

function formatDateLabel(date: string): string {
  const parsed = new Date(`${date}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return date
  return parsed.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  })
}

function shiftDate(date: string, delta: number): string {
  const parsed = new Date(`${date}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return date
  parsed.setDate(parsed.getDate() + delta)
  const y = parsed.getFullYear()
  const m = String(parsed.getMonth() + 1).padStart(2, "0")
  const d = String(parsed.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}

function CodeChip({ code }: { code: string | null }) {
  return (
    <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 font-mono text-xs font-semibold text-primary">
      {code ?? "—"}
    </span>
  )
}

function AttendanceBadge({ percentage }: { percentage: number | null }) {
  if (percentage === null) {
    return <Badge variant="muted">No attendance</Badge>
  }
  if (percentage < 75) {
    return <Badge variant="warning">Below 75%</Badge>
  }
  if (percentage < 80) {
    return <Badge variant="outline">On track</Badge>
  }
  return <Badge variant="success">Good</Badge>
}

function RecordedBadge({ statuses }: { statuses: string[] }) {
  if (statuses.length === 0) {
    return <Badge variant="muted">Not recorded</Badge>
  }
  return (
    <span className="flex flex-wrap items-center gap-1">
      {statuses.map((status, index) => (
        <Badge key={`${status}-${index}`} variant={status === "P" ? "success" : "destructive"}>
          {status === "P" ? "Present" : "Absent"}
        </Badge>
      ))}
    </span>
  )
}

function PriorityBadge({ label }: { label: string }) {
  const variant =
    label === "Critical" ? "destructive" : label === "At risk" ? "warning" : "outline"
  return <Badge variant={variant}>{label}</Badge>
}

function SessionMeta({
  session,
  className,
}: {
  session: StudentTimetableSession | DailyClass
  className?: string
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2 text-xs text-muted-foreground", className)}>
      <span className="inline-flex items-center gap-1">
        <Clock3 className="size-3" />
        {timeRange(session.start_time, session.end_time)}
      </span>
      <Badge variant="muted">Slot {session.slot_no}</Badge>
      {session.lecture_type && <Badge variant="muted">{session.lecture_type}</Badge>}
      {session.faculty_name && <span>{session.faculty_name}</span>}
    </div>
  )
}

type DayNavProps = { date: string; isFocusToday: boolean }

function DayNav({ date, isFocusToday }: DayNavProps) {
  const linkClass =
    "inline-flex min-h-8 items-center gap-1 rounded-full border px-3 text-xs font-medium transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
  return (
    <nav aria-label="Change day" className="flex flex-wrap items-center gap-1.5">
      <Link
        href="/student/timetable"
        aria-pressed={isFocusToday}
        className={cn(
          linkClass,
          isFocusToday
            ? "border-primary bg-primary text-primary-foreground"
            : "border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground",
        )}
      >
        Today
      </Link>
      <Link
        href={`/student/timetable?date=${shiftDate(date, -1)}`}
        className="border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground"
        aria-label="Previous day"
      >
        <CalendarX2 className="size-3" />
        Prev
      </Link>
      <Link
        href={`/student/timetable?date=${shiftDate(date, 1)}`}
        className="border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground"
        aria-label="Next day"
      >
        Next
        <CalendarDays className="size-3" />
      </Link>
    </nav>
  )
}

function NextClassCard({ daily }: { daily: DailyAssistantResponse }) {
  const next = daily.next_class
  return (
    <section className="flex flex-col gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Next class</h2>
        <ArrowRight className="size-4 text-muted-foreground" />
      </div>
      {!next ? (
        <p className="text-sm text-muted-foreground">No upcoming class scheduled.</p>
      ) : (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <CodeChip code={next.subject_code} />
            <p className="min-w-0 text-sm font-medium">{next.subject_name}</p>
          </div>
          <p className="inline-flex items-center gap-1 text-sm text-muted-foreground">
            <CalendarDays className="size-3" />
            {next.is_tomorrow ? "Tomorrow" : "Today"} · {timeRange(next.start_time, next.end_time)}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <AttendanceBadge percentage={next.attendance_percentage} />
            {next.is_tomorrow && <Badge variant="secondary">Slot {next.slot_no}</Badge>}
          </div>
        </div>
      )}
    </section>
  )
}

function TodayClassesCard({ classes }: { classes: DailyClass[] }) {
  return (
    <section className="flex flex-col gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Today&apos;s classes</h2>
        {classes.length > 0 && (
          <Badge variant="secondary">
            {classes.length} session{classes.length === 1 ? "" : "s"}
          </Badge>
        )}
      </div>
      {classes.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No classes are scheduled for this day.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {classes.map((session) => (
            <li
              key={`${session.subject_id}-${session.slot_no}`}
              className="flex flex-col gap-2 rounded-lg bg-muted/50 p-3 ring-1 ring-foreground/5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <CodeChip code={session.subject_code} />
                  <p className="min-w-0 text-sm font-medium">{session.subject_name}</p>
                </div>
                <RecordedBadge statuses={session.recorded_statuses} />
              </div>
              <SessionMeta session={session} />
              <div className="flex flex-wrap items-center gap-2">
                <AttendanceBadge percentage={session.attendance_percentage} />
                {session.eligibility_status === "Not Eligible" && (
                  <Badge variant="destructive">Not eligible</Badge>
                )}
                {session.performance_percentage !== null && (
                  <Badge variant="outline">Score {session.performance_percentage.toFixed(1)}%</Badge>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function FreeSlotsCard({ slots }: { slots: DailyAssistantResponse["free_slots"] }) {
  return (
    <section className="flex flex-col gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Free slots</h2>
        <Coffee className="size-4 text-muted-foreground" />
      </div>
      {slots.length === 0 ? (
        <p className="text-sm text-muted-foreground">No free slots today.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {slots.map((slot) => (
            <li
              key={slot.slot_no}
              className="flex items-center justify-between gap-2 rounded-lg bg-muted/50 px-3 py-2.5 ring-1 ring-foreground/5"
            >
              <span className="text-sm font-medium">{timeRange(slot.start_time, slot.end_time)}</span>
              <Badge variant="muted">Slot {slot.slot_no}</Badge>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function AttendanceOverview({ daily }: { daily: DailyAssistantResponse }) {
  const { semester_overall_attendance, stored_overall_attendance, note } =
    daily.attendance_context
  const statClass =
    "flex flex-col gap-1 rounded-lg bg-muted/50 p-3 ring-1 ring-foreground/5"
  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <h2 className="mb-3 text-sm font-semibold">Attendance</h2>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div className={statClass}>
          <span className="text-xs text-muted-foreground">This semester</span>
          <span className="text-xl font-semibold tabular-nums">
            {semester_overall_attendance === null
              ? "—"
              : `${semester_overall_attendance.toFixed(2)}%`}
          </span>
        </div>
        <div className={statClass}>
          <span className="text-xs text-muted-foreground">Stored overall</span>
          <span className="text-xl font-semibold tabular-nums">
            {stored_overall_attendance === null
              ? "—"
              : `${stored_overall_attendance.toFixed(2)}%`}
          </span>
        </div>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">{note}</p>
    </section>
  )
}

function StudyPriorityRow({ item }: { item: StudyPriority }) {
  return (
    <li className="flex flex-col gap-2 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <PriorityBadge label={item.priority_label} />
          <CodeChip code={item.subject_code} />
          <p className="min-w-0 text-sm font-medium">{item.subject_name}</p>
        </div>
        <span className="text-xs tabular-nums text-muted-foreground">
          {item.attendance_percentage === null
            ? "Attendance —"
            : `Attendance ${item.attendance_percentage.toFixed(2)}%`}
          {item.performance_percentage !== null &&
            ` · Score ${item.performance_percentage.toFixed(1)}%`}
        </span>
      </div>
      <ul className="flex flex-col gap-1">
        {item.reasons.map((reason) => (
          <li key={reason} className="flex items-start gap-1.5 text-sm text-muted-foreground">
            <TriangleAlert className="mt-0.5 size-3 shrink-0 text-chart-3" />
            {reason}
          </li>
        ))}
      </ul>
      {item.required_classes_to_reach_target !== null && (
        <p className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          <Target className="size-3 shrink-0" />
          Attend the next {item.required_classes_to_reach_target} classes to reach the{" "}
          {item.target_attendance.toFixed(0)}% target.
        </p>
      )}
    </li>
  )
}

function StudyPriorities({ priorities }: { priorities: StudyPriority[] }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight">Study priorities</h2>
        <p className="text-sm text-muted-foreground">
          Deterministic priorities from attendance and performance signals.
        </p>
      </div>
      {priorities.length === 0 ? (
        <div className="flex items-center gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
          <CircleCheck className="size-5 shrink-0 text-chart-2" />
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-medium">You&apos;re on track</p>
            <p className="text-sm text-muted-foreground">
              No subject is below target this semester.
            </p>
          </div>
        </div>
      ) : (
        <ol className="flex flex-col gap-2">
          {priorities.map((item) => (
            <StudyPriorityRow key={item.subject_id} item={item} />
          ))}
        </ol>
      )}
    </section>
  )
}

function DailyPriorities({ items }: { items: DailyAssistantResponse["daily_priorities"] }) {
  if (items.length === 0) return null
  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Today&apos;s focus</h2>
        <ListTodo className="size-4 text-muted-foreground" />
      </div>
      <ol className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={item.priority} className="flex items-start gap-2.5 text-sm">
            <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              {item.priority}
            </span>
            <span>{item.text}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}

type SlotRow = { slot_no: number; start_time: string; end_time: string }

function WeeklyGrid({ timetable }: { timetable: StudentTimetableResponse | null }) {
  const sessions = timetable ? timetable.days.flatMap((day) => day.sessions) : []
  const slotRows: SlotRow[] = (timetable?.slots ?? [])
    .slice()
    .sort(
      (a, b) => a.slot_no - b.slot_no || a.start_time.localeCompare(b.start_time),
    )
  const byDaySlot = new Map<string, StudentTimetableSession[]>()
  for (const session of sessions) {
    const key = `${session.day_name}::${session.slot_no}`
    const list = byDaySlot.get(key)
    if (list) list.push(session)
    else byDaySlot.set(key, [session])
  }

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight">Weekly schedule</h2>
        <p className="text-sm text-muted-foreground">
          {timetable && timetable.total_sessions > 0
            ? `Sem ${timetable.semester_no} · ${timetable.academic_year} · ${timetable.total_sessions} scheduled sessions`
            : "Your weekly timetable"}
        </p>
      </div>
      {!timetable || timetable.total_sessions === 0 ? (
        <EmptyState
          icon={CalendarDays}
          title="No timetable for your current term"
          description="A weekly timetable is not available for your current semester yet."
        />      ) : (
        <div className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
          <table className="w-full min-w-[48rem] border-separate border-spacing-0 text-sm">
            <caption className="sr-only">Weekly timetable</caption>
            <thead>
              <tr>
                <th
                  scope="col"
                  className="border-b border-r border-border/60 bg-card px-3 py-2 text-left text-xs font-semibold text-muted-foreground"
                >
                  Time
                </th>
                {DAY_NAMES.map((day) => (
                  <th
                    key={day}
                    scope="col"
                    className="border-b border-r border-border/60 bg-card px-3 py-2 text-left text-xs font-semibold text-muted-foreground"
                  >
                    {day}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {slotRows.map((slot) => (
                <tr key={slot.slot_no}>
                  <th
                    scope="row"
                    className="border-b border-r border-border/60 px-3 py-2 text-left align-top font-medium"
                  >
                    {timeRange(slot.start_time, slot.end_time)}
                  </th>
                  {DAY_NAMES.map((day) => {
                    const list = byDaySlot.get(`${day}::${slot.slot_no}`) ?? []
                    return (
                      <td
                        key={day}
                        className="border-b border-r border-border/60 px-3 py-2 align-top"
                      >
                        {list.length === 0 ? (
                          <span className="text-muted-foreground">—</span>
                        ) : (
                          <ul className="flex flex-col gap-1">
                            {list.map((session) => (
                              <li key={session.timetable_id} className="flex items-baseline gap-1.5">
                                <CodeChip code={session.subject_code} />
                                <span className="max-w-40 truncate text-xs text-muted-foreground">
                                  {session.subject_name}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function Upcoming({ daily }: { daily: DailyAssistantResponse }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight">Upcoming</h2>
        <p className="text-sm text-muted-foreground">Classes over the next two days</p>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {daily.upcoming_classes.map((day) => (
          <section
            key={day.day_name}
            className="rounded-xl bg-card p-4 ring-1 ring-foreground/10"
          >
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">
                {day.is_tomorrow ? "Tomorrow" : day.day_name}
              </h3>
              {day.sessions.length > 0 && (
                <Badge variant="secondary">
                  {day.sessions.length} session{day.sessions.length === 1 ? "" : "s"}
                </Badge>
              )}
            </div>
            {day.sessions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No classes scheduled.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {day.sessions.map((session) => (
                  <li
                    key={session.timetable_id}
                    className="flex flex-col gap-1 rounded-lg bg-muted/50 p-2.5 ring-1 ring-foreground/5"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <CodeChip code={session.subject_code} />
                      <p className="min-w-0 text-sm font-medium">{session.subject_name}</p>
                    </div>
                    <SessionMeta session={session} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>
    </section>
  )
}

function Deferrals({ daily }: { daily: DailyAssistantResponse }) {
  if (daily.deferrals.length === 0) return null
  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="flex items-start gap-2.5">
        <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold">Not available yet</h2>
          {daily.deferrals.map((deferral) => (
            <p key={deferral.feature} className="text-sm text-muted-foreground">
              {deferral.feature}: {deferral.note}
            </p>
          ))}
        </div>
      </div>
    </section>
  )
}

export function TimetableView({
  daily,
  timetable,
  fetchedAt,
}: {
  daily: DailyAssistantResponse
  timetable: StudentTimetableResponse | null
  fetchedAt?: string
}) {
  const term = daily.term
  const description = [
    `${daily.day_name}, ${formatDateLabel(daily.date)}`,
    term ? `Sem ${term.semester_no} · ${term.academic_year}` : null,
    term?.department_name,
  ]
    .filter(Boolean)
    .join(" · ")

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader
          title="Today"
          description={description}
          fetchedAt={fetchedAt}
        />
        <DayNav date={daily.date} isFocusToday={daily.is_focus_today} />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <NextClassCard daily={daily} />
        <TodayClassesCard classes={daily.today_classes} />
        <FreeSlotsCard slots={daily.free_slots} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <StudyPriorities priorities={daily.study_priorities} />
        </div>
        <div className="flex flex-col gap-4">
          <AttendanceOverview daily={daily} />
          <DailyPriorities items={daily.daily_priorities} />
        </div>
      </div>

      <WeeklyGrid timetable={timetable} />

      <Upcoming daily={daily} />

      <Deferrals daily={daily} />
    </div>
  )
}
