"use client"

import * as React from "react"
import { ArrowDownRight, ArrowUpRight, Calculator, Info } from "lucide-react"

import { simulateAttendance } from "@/lib/student/attendance-simulation"
import type { AttendanceSimulatorSubject } from "@/lib/student-api"

import { Badge } from "@/components/ui/badge"
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

type Values = { present: string; absent: string }

function parseValue(raw: string): number {
  const trimmed = raw.trim()
  if (trimmed === "") return 0
  const value = Number(trimmed)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.trunc(value))
}

function statusVariant(status: string | null): "success" | "warning" | "destructive" | "muted" {
  switch (status) {
    case "Excellent":
    case "Good":
    case "Average":
      return "success"
    case "Low":
      return "warning"
    case "Critical":
      return "destructive"
    default:
      return "muted"
  }
}

export function AttendanceSimulator({
  subjects,
  target,
}: {
  subjects: AttendanceSimulatorSubject[]
  target: number
}) {
  const withCounts = subjects.filter(
    (subject) => subject.total_classes !== null && subject.attended_classes !== null,
  )
  const [selectedId, setSelectedId] = React.useState(withCounts[0]?.subject_id ?? "")
  const [values, setValues] = React.useState<Values>({ present: "", absent: "" })

  const activeSubject =
    withCounts.find((subject) => subject.subject_id === selectedId) ?? withCounts[0]

  // Pure, deterministic and synchronous — no network, no API, no persistence.
  const result = simulateAttendance({
    total_classes: activeSubject?.total_classes ?? null,
    attended_classes: activeSubject?.attended_classes ?? null,
    hypothetical_present: parseValue(values.present),
    hypothetical_absent: parseValue(values.absent),
    target_attendance: target,
  })

  const changeSubject = (code: string | null) => {
    if (!code) return
    setSelectedId(code)
    setValues({ present: "", absent: "" })
  }

  if (withCounts.length === 0) {
    return null
  }

  const delta = result.delta
  const hasDelta = delta !== null && delta !== 0
  const deltaTone =
    hasDelta && delta !== null
      ? delta > 0
        ? "text-chart-2"
        : "text-destructive"
      : "text-muted-foreground"

  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">Attendance simulator</h2>
          <p className="mt-1 flex items-start gap-1.5 text-xs text-muted-foreground">
            <Info className="mt-0.5 size-3 shrink-0" />
            Simulation only — does not change your attendance record.
          </p>
        </div>
        <Badge variant="muted">
          <Calculator className="size-3" />
          Hypothetical
        </Badge>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="sim-att-subject" className="text-xs font-medium text-muted-foreground">
            Subject
          </label>
          <Select value={activeSubject?.subject_id ?? null} onValueChange={changeSubject}>
            <SelectTrigger id="sim-att-subject" className="w-full sm:w-80">
              <SelectValue>
                {(selected: string | null) =>
                  withCounts.find((subject) => subject.subject_id === selected)
                    ?.subject_name ?? "Select subject"
                }
              </SelectValue>
              <SelectIcon />
            </SelectTrigger>
            <SelectContent>
              <SelectList>
                {withCounts.map((subject) => (
                  <SelectItem key={subject.subject_id} value={subject.subject_id}>
                    {subject.subject_code} · {subject.subject_name}
                  </SelectItem>
                ))}
              </SelectList>
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="sim-att-present" className="text-xs font-medium text-muted-foreground">
              Attend next
            </label>
            <Input
              id="sim-att-present"
              type="number"
              min={0}
              max={100}
              inputMode="numeric"
              placeholder="0"
              value={values.present}
              onChange={(event) => setValues({ ...values, present: event.target.value })}
            />
            <p className="text-xs text-muted-foreground">
              Classes you plan to attend (assumed present).
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="sim-att-absent" className="text-xs font-medium text-muted-foreground">
              Miss next
            </label>
            <Input
              id="sim-att-absent"
              type="number"
              min={0}
              max={100}
              inputMode="numeric"
              placeholder="0"
              value={values.absent}
              onChange={(event) => setValues({ ...values, absent: event.target.value })}
            />
            <p className="text-xs text-muted-foreground">
              Classes you plan to skip (assumed absent).
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3 rounded-lg bg-muted/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase">
              Simulated result
            </p>
            {result.complete && (
              <p className="text-xs tabular-nums text-muted-foreground">
                {result.attended_classes} of {result.total_classes} classes attended
              </p>
            )}
          </div>

          {!result.complete ? (
            <p className="text-sm text-muted-foreground">
              Attendance baseline is unavailable for this subject.
            </p>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div>
                  <p className="text-xs text-muted-foreground">Current attendance</p>
                  <p className="mt-0.5 text-xl font-semibold tabular-nums">
                    {result.current_attendance?.toFixed(1) ?? "—"}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Projected attendance</p>
                  <p className="mt-0.5 flex items-center gap-1.5 text-xl font-semibold tabular-nums">
                    {result.resulting_attendance?.toFixed(1) ?? "—"}%
                    {hasDelta && delta !== null && (
                      <span className={`flex items-center gap-0.5 text-xs font-medium ${deltaTone}`}>
                        {delta > 0 ? (
                          <ArrowUpRight className="size-3" />
                        ) : (
                          <ArrowDownRight className="size-3" />
                        )}
                        {delta > 0 ? "+" : ""}
                        {delta.toFixed(2)}%
                      </span>
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Status</p>
                  <p className="mt-0.5">
                    <Badge variant={statusVariant(result.attendance_status)}>
                      {result.attendance_status ?? "—"}
                    </Badge>
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Eligibility</p>
                  <p className="mt-0.5">
                    <Badge
                      variant={
                        result.eligibility_status === "Eligible" ? "success" : "destructive"
                      }
                    >
                      {result.eligibility_status ?? "—"}
                    </Badge>
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-lg bg-background/60 p-3">
                  <p className="text-xs text-muted-foreground">
                    To reach the {target.toFixed(0)}% target
                  </p>
                  <p className="mt-0.5 text-sm font-medium tabular-nums">
                    {result.classes_to_reach_target === 0 ? (
                      "Already at or above target"
                    ) : (
                      <>
                        Attend the next {result.classes_to_reach_target}{" "}
                        {result.classes_to_reach_target === 1 ? "class" : "classes"}
                      </>
                    )}
                  </p>
                </div>
                <div className="rounded-lg bg-background/60 p-3">
                  <p className="text-xs text-muted-foreground">
                    Before falling below {target.toFixed(0)}%
                  </p>
                  <p className="mt-0.5 text-sm font-medium tabular-nums">
                    {result.classes_to_skip_below_target === 0 ? (
                      "Cannot miss any class"
                    ) : (
                      <>
                        You can miss {result.classes_to_skip_below_target}{" "}
                        {result.classes_to_skip_below_target === 1 ? "class" : "classes"}
                      </>
                    )}
                  </p>
                </div>
              </div>

              <p className="text-sm text-muted-foreground">{result.message}</p>
            </>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setValues({ present: "", absent: "" })}
            >
              Reset
            </Button>
            <p className="text-xs text-muted-foreground">
              No changes are written to your attendance record.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
