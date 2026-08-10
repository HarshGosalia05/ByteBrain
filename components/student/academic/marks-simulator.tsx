"use client"

import * as React from "react"
import { Calculator, Info, TriangleAlert } from "lucide-react"

import {
  MARKS_COMPONENT_RANGE,
  MARKS_TOTAL_MAX,
  parseMarksField,
  simulateMarks,
  type MarksComponentKey,
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

export type SimulatorSubject = {
  subject_code: string
  subject_name: string
  internal_marks: number | null
  mid_sem_marks: number | null
  end_sem_marks: number | null
}

type Values = Record<MarksComponentKey, string>

// UI field order and the snake_case component each maps to.
const FIELD_KEYS: MarksComponentKey[] = ["internal_marks", "mid_sem_marks", "end_sem_marks"]

function valuesFromSubject(subject: SimulatorSubject): Values {
  return {
    internal_marks: subject.internal_marks === null ? "" : String(subject.internal_marks),
    mid_sem_marks: subject.mid_sem_marks === null ? "" : String(subject.mid_sem_marks),
    end_sem_marks: subject.end_sem_marks === null ? "" : String(subject.end_sem_marks),
  }
}

const EMPTY_VALUES: Values = { internal_marks: "", mid_sem_marks: "", end_sem_marks: "" }

function emptyErrors(): Record<MarksComponentKey, string> {
  return { internal_marks: "", mid_sem_marks: "", end_sem_marks: "" }
}

// Block single-character keys that are not digits. Control keys (Backspace,
// Delete, Arrows, Tab, Enter, Home, End) have multi-character `key` values and
// pass through. Copy/paste/cut/select-all shortcuts are allowed so the paste
// path is still validated by the onChange sanitizer below.
function guardNumericKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
  if (event.ctrlKey || event.metaKey || event.altKey) return
  if (event.key.length === 1 && !/[0-9]/.test(event.key)) {
    event.preventDefault()
  }
}

export function MarksSimulator({ subjects }: { subjects: SimulatorSubject[] }) {
  const first = subjects[0]
  const [selectedCode, setSelectedCode] = React.useState(first?.subject_code ?? "")
  const [values, setValues] = React.useState<Values>(() =>
    first ? valuesFromSubject(first) : EMPTY_VALUES,
  )
  const [fieldErrors, setFieldErrors] = React.useState<Record<MarksComponentKey, string>>(() =>
    emptyErrors(),
  )

  const activeSubject =
    subjects.find((subject) => subject.subject_code === selectedCode) ?? first

  // The state is always either "" or a valid in-range integer (see handleChange
  // below). simulateMarks still hard-validates as defense in depth.
  const result: MarksSimulationResult = simulateMarks({
    internal_marks: values.internal_marks === "" ? null : Number(values.internal_marks),
    mid_sem_marks: values.mid_sem_marks === "" ? null : Number(values.mid_sem_marks),
    end_sem_marks: values.end_sem_marks === "" ? null : Number(values.end_sem_marks),
  })

  const hasFieldError =
    fieldErrors.internal_marks !== "" ||
    fieldErrors.mid_sem_marks !== "" ||
    fieldErrors.end_sem_marks !== ""

  const canShowResult = !hasFieldError && result.status === "complete"

  const handleChange = (field: MarksComponentKey, raw: string) => {
    const parsed = parseMarksField(raw, field)
    if (parsed.valid) {
      setValues((prev) => ({
        ...prev,
        [field]: parsed.value === null ? "" : String(parsed.value),
      }))
      setFieldErrors((prev) => ({ ...prev, [field]: "" }))
    } else {
      setFieldErrors((prev) => ({ ...prev, [field]: parsed.error ?? "" }))
    }
  }

  const changeSubject = (code: string | null) => {
    if (!code) return
    const subject = subjects.find((item) => item.subject_code === code)
    if (!subject) return
    setSelectedCode(code)
    setValues(valuesFromSubject(subject))
    setFieldErrors(emptyErrors())
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
          {FIELD_KEYS.map((field) => {
            const range = MARKS_COMPONENT_RANGE[field]
            const error = fieldErrors[field]
            return (
              <div key={field} className="flex flex-col gap-1.5">
                <label
                  htmlFor={`sim-${field}`}
                  className="text-xs font-medium text-muted-foreground"
                >
                  {range.label} marks{" "}
                  <span className="text-muted-foreground/70">/ {range.max}</span>
                </label>
                <Input
                  id={`sim-${field}`}
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  autoComplete="off"
                  placeholder="Not entered"
                  value={values[field]}
                  onChange={(event) => handleChange(field, event.target.value)}
                  onKeyDown={guardNumericKeyDown}
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? `sim-${field}-error` : undefined}
                />
                {error ? (
                  <p id={`sim-${field}-error`} className="text-[11px] leading-tight text-destructive">
                    {error}
                  </p>
                ) : field === "end_sem_marks" && result.end_sem_min_warning ? (
                  <p
                    id="sim-end_sem_marks-warning"
                    className="flex items-start gap-1 text-[11px] leading-tight text-amber-600 dark:text-amber-400"
                  >
                    <TriangleAlert className="mt-px size-3 shrink-0" />
                    End-Sem marks must be at least {result.status === "complete" ? "18 to pass." : "18."}
                  </p>
                ) : null}
              </div>
            )
          })}
        </div>

        <div className="flex flex-col gap-3 rounded-lg bg-muted/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase">
              Simulated result
            </p>
          </div>

          {!canShowResult ? (
            <p className="text-sm text-muted-foreground">
              Enter valid marks for all three components to see the simulated result.
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

          {result.end_sem_min_warning && result.status === "complete" ? (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              End-Sem marks must be at least 18 to pass. The simulated result cannot be Pass.
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                if (activeSubject) {
                  setValues(valuesFromSubject(activeSubject))
                  setFieldErrors(emptyErrors())
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
