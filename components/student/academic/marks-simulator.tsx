"use client"

import * as React from "react"
import { Calculator, Info } from "lucide-react"

import {
  MARKS_TOTAL_MAX,
  simulateMarks,
  type MarksSimulationResult,
} from "@/lib/student/marks-simulation"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectIcon,
  SelectItem,
  SelectList,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { GradeBadge } from "@/components/shared/data/grade-badge"

// Verified assessment model (MD-03 brief §4): Internal /20, Mid-Sem /50,
// End-Sem /70, Total /140. Display-only labels (mirrors the shared
// lib/student/marks-simulation.ts maxima).
const COMPONENT_MAX = {
  internal: 20,
  mid: 50,
  end: 70,
} as const

export type SimulatorSubject = {
  subject_code: string
  subject_name: string
  internal_marks: number | null
  mid_sem_marks: number | null
  end_sem_marks: number | null
}

type Values = { internal: string; mid: string; end: string }

function valuesFromSubject(subject: SimulatorSubject): Values {
  return {
    internal: subject.internal_marks === null ? "" : String(subject.internal_marks),
    mid: subject.mid_sem_marks === null ? "" : String(subject.mid_sem_marks),
    end: subject.end_sem_marks === null ? "" : String(subject.end_sem_marks),
  }
}

function parseValue(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === "") return null
  const value = Number(trimmed)
  if (!Number.isFinite(value)) return null
  return Math.trunc(value)
}

export function MarksSimulator({ subjects }: { subjects: SimulatorSubject[] }) {
  const first = subjects[0]
  const [selectedCode, setSelectedCode] = React.useState(first?.subject_code ?? "")
  const [values, setValues] = React.useState<Values>(() =>
    first ? valuesFromSubject(first) : { internal: "", mid: "", end: "" },
  )

  const activeSubject =
    subjects.find((subject) => subject.subject_code === selectedCode) ?? first

  // Pure, deterministic and synchronous — no network, no API, no persistence.
  const result: MarksSimulationResult = simulateMarks({
    internal_marks: parseValue(values.internal),
    mid_sem_marks: parseValue(values.mid),
    end_sem_marks: parseValue(values.end),
  })

  const changeSubject = (code: string | null) => {
    if (!code) return
    const subject = subjects.find((item) => item.subject_code === code)
    if (!subject) return
    setSelectedCode(code)
    setValues(valuesFromSubject(subject))
  }

  if (subjects.length === 0) {
    return null
  }

  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">Marks simulator</h2>
          <p className="mt-1 flex items-start gap-1.5 text-xs text-muted-foreground">
            <Info className="mt-0.5 size-3 shrink-0" />
            Simulation only — does not change your academic record.
          </p>
        </div>
        <Badge variant="muted">
          <Calculator className="size-3" />
          Hypothetical
        </Badge>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="sim-subject" className="text-xs font-medium text-muted-foreground">
            Subject
          </label>
          <Select value={activeSubject?.subject_code ?? null} onValueChange={changeSubject}>
            <SelectTrigger id="sim-subject" className="w-full sm:w-80">
              <SelectValue>
                {(selected: string | null) =>
                  subjects.find((subject) => subject.subject_code === selected)?.subject_name ??
                  "Select subject"
                }
              </SelectValue>
              <SelectIcon />
            </SelectTrigger>
            <SelectContent>
              <SelectList>
                {subjects.map((subject) => (
                  <SelectItem key={subject.subject_code} value={subject.subject_code}>
                    {subject.subject_code} · {subject.subject_name}
                  </SelectItem>
                ))}
              </SelectList>
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="sim-internal" className="text-xs font-medium text-muted-foreground">
              Internal marks <span className="text-muted-foreground/70">/ {COMPONENT_MAX.internal}</span>
            </label>
            <Input
              id="sim-internal"
              type="number"
              min={0}
              max={COMPONENT_MAX.internal}
              inputMode="numeric"
              value={values.internal}
              onChange={(event) => setValues({ ...values, internal: event.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="sim-mid" className="text-xs font-medium text-muted-foreground">
              Mid-sem marks <span className="text-muted-foreground/70">/ {COMPONENT_MAX.mid}</span>
            </label>
            <Input
              id="sim-mid"
              type="number"
              min={0}
              max={COMPONENT_MAX.mid}
              inputMode="numeric"
              value={values.mid}
              onChange={(event) => setValues({ ...values, mid: event.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="sim-end" className="text-xs font-medium text-muted-foreground">
              End-sem marks <span className="text-muted-foreground/70">/ {COMPONENT_MAX.end}</span>
            </label>
            <Input
              id="sim-end"
              type="number"
              min={0}
              max={COMPONENT_MAX.end}
              inputMode="numeric"
              value={values.end}
              onChange={(event) => setValues({ ...values, end: event.target.value })}
            />
          </div>
        </div>

        <div className="flex flex-col gap-3 rounded-lg bg-muted/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase">
              Simulated result
            </p>
          </div>

          {!result.complete ? (
            <p className="text-sm text-muted-foreground">
              Enter values for all three components (or adjust your end-sem marks) to see the
              simulated outcome.
            </p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div>
                <p className="text-xs text-muted-foreground">Total (of {MARKS_TOTAL_MAX})</p>
                <p className="mt-0.5 text-xl font-semibold tabular-nums">
                  {result.total_marks?.toFixed(0) ?? "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Percentage</p>
                <p className="mt-0.5 text-xl font-semibold tabular-nums">
                  {result.percentage !== null ? `${result.percentage.toFixed(2)}%` : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Grade</p>
                <p className="mt-0.5">
                  <GradeBadge grade={result.grade} />
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Result</p>
                <p className="mt-0.5">
                  <Badge
                    variant={
                      result.result_status?.toUpperCase() === "PASS"
                        ? "success"
                        : result.result_status?.toUpperCase() === "FAIL"
                          ? "destructive"
                          : "muted"
                    }
                  >
                    {result.result_status ?? "—"}
                  </Badge>
                </p>
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                if (activeSubject) {
                  setValues(valuesFromSubject(activeSubject))
                }
              }}
            >
              Reset to actual marks
            </Button>
            <p className="text-xs text-muted-foreground">
              No changes are written to your academic record.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
