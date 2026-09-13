"use client"

import Link from "next/link"
import { CalendarDays, Clock, GraduationCap } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/state/empty-state"
import type {
  FacultyTimetableDay,
  FacultyTimetableResponse,
  FacultyTimetableSession,
  FullTimetableResponse,
} from "@/lib/faculty-api"
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

type SlotRow = { slot_no: number; start_time: string; end_time: string }

function formatTime(value: string): string {
  if (!value) return ""
  const [hours, minutes] = value.split(":")
  if (hours === undefined || minutes === undefined) return value
  return `${hours}:${minutes}`
}

function timeRange(start: string, end: string): string {
  return `${formatTime(start)}–${formatTime(end)}`
}

const termChip =
  "inline-flex min-h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
const termChipActive = "border-primary bg-primary text-primary-foreground"
const termChipIdle = "border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground"

function TermChips({
  semester,
  semesterOptions,
}: {
  semester: number | null
  semesterOptions: number[]
}) {
  const hrefFor = (sem: number | null) =>
    sem === null ? "/faculty/timetable" : `/faculty/timetable?semester=${sem}`

  return (
    <div role="group" aria-label="Filter by semester" className="flex flex-wrap items-center gap-1.5">
      {semesterOptions.map((sem) => (
        <Link
          key={sem}
          href={hrefFor(sem)}
          aria-pressed={semester === sem}
          className={cn(termChip, semester === sem ? termChipActive : termChipIdle)}
        >
          Sem {sem}
        </Link>
      ))}
    </div>
  )
}

function PageHeader({
  data,
  semester,
  semesterOptions,
}: {
  data: FacultyTimetableResponse
  semester: number | null
  semesterOptions: number[]
}) {
  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-2xl font-semibold tracking-tight">Time Table</h1>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Sem {data.semester_no} · {data.academic_year} · {data.total_sessions} scheduled session
          {data.total_sessions === 1 ? "" : "s"}
        </p>
        <TermChips semester={semester} semesterOptions={semesterOptions} />
      </div>
    </section>
  )
}

export function TimetableView({
  data,
  fullTimetable,
  semester,
  semesterOptions,
}: {
  data: FacultyTimetableResponse
  fullTimetable: FullTimetableResponse | null
  semester: number | null
  semesterOptions: number[]
}) {
  const sessions = data.days.flatMap((day) => day.sessions)

  // Complete slot grid from the timetable data (all available time periods),
  // falling back to the slots present in this faculty's sessions if the API
  // response does not include the full slot list.
  const slotRows: SlotRow[] =
    data.slots && data.slots.length > 0
      ? [...data.slots]
          .sort(
            (a, b) =>
              a.slot_no - b.slot_no ||
              a.start_time.localeCompare(b.start_time) ||
              a.end_time.localeCompare(b.end_time),
          )
          .map((slot) => ({
            slot_no: slot.slot_no,
            start_time: slot.start_time,
            end_time: slot.end_time,
          }))
      : sessions
          .map((session) => ({
            slot_no: session.slot_no,
            start_time: session.start_time,
            end_time: session.end_time,
          }))
          .filter(
            (slot, index, self) => self.findIndex((other) => other.slot_no === slot.slot_no) === index,
          )
          .sort(
            (a, b) =>
              a.slot_no - b.slot_no ||
              a.start_time.localeCompare(b.start_time) ||
              a.end_time.localeCompare(b.end_time),
          )

  // day_name :: slot_no -> sessions (keeps multiple lectures in the same slot).
  const byDaySlot = new Map<string, FacultyTimetableSession[]>()
  for (const session of sessions) {
    const key = `${session.day_name}::${session.slot_no}`
    const list = byDaySlot.get(key)
    if (list) list.push(session)
    else byDaySlot.set(key, [session])
  }
  for (const list of byDaySlot.values()) {
    list.sort(
      (a, b) => a.start_time.localeCompare(b.start_time) || a.slot_no - b.slot_no,
    )
  }

  // Full semester timetable (all subjects, every faculty) - no faculty filter.
  const fullSessions = fullTimetable ? fullTimetable.days.flatMap((day) => day.sessions) : []
  const fullSlotRows: SlotRow[] =
    fullTimetable && fullTimetable.slots.length > 0
      ? [...fullTimetable.slots]
          .sort(
            (a, b) =>
              a.slot_no - b.slot_no ||
              a.start_time.localeCompare(b.start_time) ||
              a.end_time.localeCompare(b.end_time),
          )
          .map((slot) => ({
            slot_no: slot.slot_no,
            start_time: slot.start_time,
            end_time: slot.end_time,
          }))
      : fullSessions
          .map((session) => ({
            slot_no: session.slot_no,
            start_time: session.start_time,
            end_time: session.end_time,
          }))
          .filter(
            (slot, index, self) => self.findIndex((other) => other.slot_no === slot.slot_no) === index,
          )
          .sort(
            (a, b) =>
              a.slot_no - b.slot_no ||
              a.start_time.localeCompare(b.start_time) ||
              a.end_time.localeCompare(b.end_time),
          )

  const fullByDaySlot = new Map<string, FacultyTimetableSession[]>()
  for (const session of fullSessions) {
    const key = `${session.day_name}::${session.slot_no}`
    const list = fullByDaySlot.get(key)
    if (list) list.push(session)
    else fullByDaySlot.set(key, [session])
  }
  for (const list of fullByDaySlot.values()) {
    list.sort(
      (a, b) => a.start_time.localeCompare(b.start_time) || a.slot_no - b.slot_no,
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader data={data} semester={semester} semesterOptions={semesterOptions} />

      {data.total_sessions === 0 ? (
        <EmptyState
          icon={CalendarDays}
          title="No Timetable"
          description="No weekly timetable sessions are scheduled for you in this term yet."
        />
      ) : (
        <>
          {/* ------------------------------------------------------------------ */}
          {/* 1. Existing scheduled session cards                                */}
          {/* ------------------------------------------------------------------ */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.days.map((day: FacultyTimetableDay) => (
              <section
                key={day.day_name}
                className="flex flex-col gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10"
              >
                <h2 className="text-sm font-semibold">{day.day_name}</h2>
                <ul className="flex flex-col gap-2">
                  {day.sessions.map((session) => (
                    <li
                      key={session.timetable_id}
                      className="rounded-lg bg-muted/50 p-3 ring-1 ring-foreground/5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="min-w-0 text-sm font-medium">
                          {session.subject_code ? `${session.subject_code} · ` : ""}
                          {session.subject_name}
                        </p>
                        <Badge variant="secondary">
                          <Clock className="mr-1 size-3" />
                          Slot {session.slot_no}
                        </Badge>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span>
                          {formatTime(session.start_time)}–{formatTime(session.end_time)}
                        </span>
                        {session.lecture_type && (
                          <Badge variant="muted">{session.lecture_type}</Badge>
                        )}
                        {session.credits !== null && session.credits !== undefined && (
                          <span className="inline-flex items-center gap-1">
                            <GraduationCap className="size-3" />
                            {session.credits} credit{session.credits === 1 ? "" : "s"}
                          </span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>

          {/* ------------------------------------------------------------------ */}
          {/* 2. Weekly Schedule (quick overview)                                 */}
          {/* ------------------------------------------------------------------ */}
          <section className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <h2 className="text-lg font-semibold tracking-tight">Weekly Schedule</h2>
              <p className="text-sm text-muted-foreground">Quick weekly overview</p>
            </div>
            <div className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
              <table className="w-full min-w-[48rem] border-separate border-spacing-0 text-sm">
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
                                  <li
                                    key={session.timetable_id}
                                    className="flex items-baseline gap-1.5"
                                  >
                                    <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 font-mono text-xs font-semibold text-primary">
                                      {session.subject_code ?? session.subject_id}
                                    </span>
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
          </section>
        </>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* 3. Full Timetable (complete semester weekly grid)                    */}
      {/* ------------------------------------------------------------------ */}
      <section className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold tracking-tight">Full Timetable</h2>
          <p className="text-sm text-muted-foreground">
            {fullTimetable
              ? `Complete Semester ${fullTimetable.semester_no} · ${fullTimetable.academic_year} timetable for all subjects`
              : "Complete weekly teaching schedule"}
          </p>
        </div>
        {!fullTimetable ? (
          <div className="rounded-xl bg-card p-6 text-sm text-muted-foreground ring-1 ring-foreground/10">
            Full timetable could not be loaded.
          </div>
        ) : fullTimetable.total_sessions === 0 ? (
          <div className="rounded-xl bg-card p-6 text-sm text-muted-foreground ring-1 ring-foreground/10">
            No timetable records found for Semester {fullTimetable.semester_no} ·{" "}
            {fullTimetable.academic_year}.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
            <table className="w-full min-w-[68rem] border-separate border-spacing-0 text-sm">
              <thead>
                <tr>
                  <th
                    scope="col"
                    className="sticky left-0 z-20 border-b border-r border-border/60 bg-card px-3 py-2 text-left text-xs font-semibold text-muted-foreground"
                  >
                    Time / Slot
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
                {fullSlotRows.map((slot) => (
                  <tr key={slot.slot_no}>
                    <th
                      scope="row"
                      className="sticky left-0 z-10 border-b border-r border-border/60 bg-card px-3 py-3 text-left align-top"
                    >
                      <p className="text-sm font-semibold">Slot {slot.slot_no}</p>
                      <p className="text-xs text-muted-foreground">
                        {timeRange(slot.start_time, slot.end_time)}
                      </p>
                    </th>
                    {DAY_NAMES.map((day) => {
                      const list = fullByDaySlot.get(`${day}::${slot.slot_no}`) ?? []
                      return (
                        <td
                          key={day}
                          className="border-b border-r border-border/60 px-2 py-2 align-top"
                        >
                          {list.length === 0 ? (
                            <span className="text-muted-foreground">—</span>
                          ) : (
                            <div className="flex flex-col gap-2">
                              {list.map((session) => (
                                <div
                                  key={session.timetable_id}
                                  className="rounded-lg bg-muted/50 p-2.5 ring-1 ring-foreground/5"
                                >
                                  <p className="font-mono text-xs font-semibold text-primary">
                                    {session.subject_code ?? session.subject_id}
                                  </p>
                                  <p className="mt-0.5 text-sm leading-snug font-medium">
                                    {session.subject_name}
                                  </p>
                                  <p className="mt-1 text-xs text-muted-foreground">
                                    <Clock className="mr-1 inline size-3" />
                                    {timeRange(session.start_time, session.end_time)}
                                  </p>
                                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                                    {session.lecture_type && (
                                      <Badge variant="muted">{session.lecture_type}</Badge>
                                    )}
                                    {session.credits !== null &&
                                      session.credits !== undefined && (
                                        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                                          <GraduationCap className="size-3" />
                                          {session.credits} credit
                                          {session.credits === 1 ? "" : "s"}
                                        </span>
                                      )}
                                  </div>
                                </div>
                              ))}
                            </div>
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
    </div>
  )
}
