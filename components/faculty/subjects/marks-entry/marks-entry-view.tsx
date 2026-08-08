"use client"

import * as React from "react"
import Link from "next/link"
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardList,
  LoaderCircle,
  RefreshCw,
  Save,
  TriangleAlert,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { GradeBadge } from "@/components/shared/data/grade-badge"
import { FreshnessBadge } from "@/components/shared/data/freshness-badge"
import { EmptyState } from "@/components/shared/state/empty-state"
import type {
  MarksBatchSaveRequest,
  MarksBatchSaveResponse,
  MarksRowInput,
  SubjectMarksGrid,
  SubjectMarksRow,
} from "@/lib/faculty-api"

import { MarksChangeHistory } from "./marks-change-history"

type CellDraft = {
  internal?: string
  mid?: string
  end?: string
  remarks?: string
}

type FieldIssue = {
  enrollment_record_id: string
  label: string
  message: string
}

function parseNumber(text: string | undefined): number | null | "invalid" {
  if (text === undefined || text.trim() === "") return null
  const parsed = Number(text)
  if (!Number.isFinite(parsed)) return "invalid"
  return parsed
}

function formatPercent(value: number | null): string {
  return value !== null ? `${value.toFixed(1)}%` : "—"
}

function fieldDraftValue(
  row: SubjectMarksRow,
  draft: CellDraft | undefined,
  field: keyof CellDraft,
): string {
  if (draft && draft[field] !== undefined) return draft[field]
  const value = row[field as keyof SubjectMarksRow]
  return value === null || value === undefined ? "" : String(value)
}

function marksMaxima(config: SubjectMarksGrid["config"]) {
  return [
    { label: "Internal", max: config.internal_max },
    { label: "Mid-sem", max: config.mid_sem_max },
    { label: "End-sem", max: config.end_sem_max },
    { label: "Total", max: config.total_max },
  ]
}

export function MarksEntryView({
  subjectId,
  initialGrid,
  fetchedAt: initialFetchedAt,
  semester,
  academicYear,
}: {
  subjectId: string
  initialGrid: SubjectMarksGrid
  fetchedAt: string | null
  semester?: number
  academicYear?: string
}) {
  const [grid, setGrid] = React.useState(initialGrid)
  const [fetchedAt, setFetchedAt] = React.useState<string | null>(initialFetchedAt)
  const [drafts, setDrafts] = React.useState<Record<string, CellDraft>>({})
  const [activeTab, setActiveTab] = React.useState("grid")
  const [saving, setSaving] = React.useState(false)
  const [refreshing, setRefreshing] = React.useState(false)
  const [saveError, setSaveError] = React.useState<string | null>(null)
  const [summary, setSummary] = React.useState<MarksBatchSaveResponse["summary"] | null>(null)
  const [loadError, setLoadError] = React.useState<string | null>(null)

  const config = grid.config
  const queryString = React.useMemo(() => {
    const params = new URLSearchParams()
    if (semester !== undefined) params.set("semester", String(semester))
    if (academicYear) params.set("academic_year", academicYear)
    return params.toString()
  }, [semester, academicYear])

  const draftCount = Object.keys(drafts).length

  function setField(
    enrollmentRecordId: string,
    field: keyof CellDraft,
    value: string,
  ) {
    setDrafts((prev) => {
      const next = { ...prev }
      const existing = { ...(next[enrollmentRecordId] ?? {}) }
      if (value === "") {
        delete existing[field]
        if (Object.keys(existing).length === 0) {
          delete next[enrollmentRecordId]
        } else {
          next[enrollmentRecordId] = existing
        }
      } else {
        existing[field] = value
        next[enrollmentRecordId] = existing
      }
      return next
    })
  }

  function validateDrafts(): FieldIssue[] {
    const issues: FieldIssue[] = []
    for (const [enrollmentRecordId, draft] of Object.entries(drafts)) {
      const row = grid.rows.find((r) => r.enrollment_record_id === enrollmentRecordId)
      if (!row) continue
      const label = `${row.enrollment_no} · ${row.first_name} ${row.last_name}`
      const specs: Array<[keyof CellDraft, number, string]> = [
        ["internal", config.internal_max, "Internal marks"],
        ["mid", config.mid_sem_max, "Mid-sem marks"],
        ["end", config.end_sem_max, "End-sem marks"],
      ]
      for (const [field, max, name] of specs) {
        const raw = draft[field]
        if (raw === undefined) continue
        const parsed = parseNumber(raw)
        if (parsed === "invalid") {
          issues.push({
            enrollment_record_id: enrollmentRecordId,
            label,
            message: `${name}: "${raw.trim()}" is not a valid number.`,
          })
        } else if (parsed !== null) {
          if (!Number.isInteger(parsed)) {
            issues.push({
              enrollment_record_id: enrollmentRecordId,
              label,
              message: `${name}: must be a whole number.`,
            })
          } else if (parsed < 0 || parsed > max) {
            issues.push({
              enrollment_record_id: enrollmentRecordId,
              label,
              message: `${name}: must be between 0 and ${max}.`,
            })
          }
        }
      }
      if (
        draft.remarks !== undefined &&
        draft.remarks.length > config.remarks_max_length
      ) {
        issues.push({
          enrollment_record_id: enrollmentRecordId,
          label,
          message: `Remarks: must be at most ${config.remarks_max_length} characters.`,
        })
      }
    }
    return issues
  }

  async function refreshGrid() {
    setRefreshing(true)
    setLoadError(null)
    try {
      const suffix = queryString ? `?${queryString}&refresh=1` : "?refresh=1"
      const res = await fetch(`/api/faculty/subjects/${subjectId}/marks${suffix}`, {
        cache: "no-store",
      })
      const result = (await res.json()) as
        | { ok: true; data: SubjectMarksGrid; fetchedAt: string | null }
        | { ok: false; error: { status: number; message: string } }
      if (!result.ok) {
        setLoadError(result.error.message)
        return
      }
      setGrid(result.data)
      setFetchedAt(result.fetchedAt)
      setDrafts({})
      setSummary(null)
      setSaveError(null)
    } catch {
      setLoadError("Could not refresh the marks grid. Please try again.")
    } finally {
      setRefreshing(false)
    }
  }

  async function handleSave() {
    const issues = validateDrafts()
    if (issues.length > 0) {
      setSaveError(
        `Cannot save — fix ${issues.length} issue${issues.length === 1 ? "" : "s"} first.`,
      )
      return
    }
    const rows: MarksRowInput[] = Object.entries(drafts).map(
      ([enrollmentRecordId, draft]) => {
        const row: MarksRowInput = { enrollment_record_id: enrollmentRecordId }
        if (draft.internal !== undefined) {
          row.internal_marks = parseNumber(draft.internal) as number | null
        }
        if (draft.mid !== undefined) {
          row.mid_sem_marks = parseNumber(draft.mid) as number | null
        }
        if (draft.end !== undefined) {
          row.end_sem_marks = parseNumber(draft.end) as number | null
        }
        if (draft.remarks !== undefined) {
          row.remarks = draft.remarks
        }
        return row
      },
    )
    const payload: MarksBatchSaveRequest = {
      semester_no: grid.semester_no,
      academic_year: grid.academic_year,
      rows,
    }
    setSaving(true)
    setSaveError(null)
    setSummary(null)
    try {
      const res = await fetch(`/api/faculty/subjects/${subjectId}/marks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        cache: "no-store",
      })
      const result = (await res.json()) as
        | { ok: true; data: MarksBatchSaveResponse; fetchedAt: string | null }
        | { ok: false; error: { status: number; message: string } }
      if (!result.ok) {
        setSaveError(result.error.message)
        return
      }
      setGrid(result.data.grid)
      setFetchedAt(result.fetchedAt)
      setSummary(result.data.summary)
      setDrafts({})
    } catch {
      setSaveError("Could not save marks. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  const issues = validateDrafts()

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <Link
          href={`/faculty/subjects/${subjectId}`}
          className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to subject
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-mono text-xs text-muted-foreground">{grid.subject_code}</p>
              <Badge variant="secondary">{grid.credits ?? "—"} credits</Badge>
            </div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">{grid.subject_name}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Marks entry · Sem {grid.semester_no} · {grid.academic_year}
              {grid.department_name ? ` · ${grid.department_name}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <FreshnessBadge fetchedAt={fetchedAt} />
            <Button
              variant="outline"
              size="sm"
              onClick={() => void refreshGrid()}
              disabled={refreshing}
            >
              {refreshing ? (
                <LoaderCircle className="size-3.5 animate-spin" />
              ) : (
                <RefreshCw className="size-3.5" />
              )}
              Refresh
            </Button>
          </div>
        </div>
      </section>

      <section
        className="flex flex-wrap items-center gap-2 rounded-xl bg-card p-4 ring-1 ring-foreground/10"
        aria-label="Maxima"
      >
        {marksMaxima(config).map((item) => (
          <Badge key={item.label} variant="muted">
            {item.label} ≤ {item.max}
          </Badge>
        ))}
        <Badge variant="muted">Pass ≥ {config.pass_percentage}%</Badge>
      </section>

      {loadError && (
        <section
          className="flex flex-wrap items-center gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4"
          role="alert"
        >
          <TriangleAlert className="size-4 text-destructive" />
          <p className="text-sm text-destructive">{loadError}</p>
        </section>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList>
          <TabsTrigger value="grid">Entry grid</TabsTrigger>
          <TabsTrigger value="history">Change history</TabsTrigger>
        </TabsList>

        <TabsContent value="grid">
          <div className="flex flex-col gap-4">
            {issues.length > 0 && (
              <section
                className="rounded-xl border border-destructive/30 bg-destructive/5 p-4"
                role="alert"
              >
                <div className="flex items-center gap-2">
                  <TriangleAlert className="size-4 text-destructive" />
                  <p className="text-sm font-medium text-destructive">
                    Fix the following before saving:
                  </p>
                </div>
                <ul className="mt-2 flex list-inside list-disc flex-col gap-1 text-sm text-muted-foreground">
                  {issues.map((issue, index) => (
                    <li key={`${issue.enrollment_record_id}-${index}`}>
                      <span className="font-medium text-foreground">{issue.label}:</span>{" "}
                      {issue.message}
                    </li>
                  ))}
                </ul>
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

            {grid.rows.length === 0 ? (
              <EmptyState
                icon={ClipboardList}
                title="No marks to display"
                description="No enrollment rows are available in this subject and term scope."
              />
            ) : (
              <div className="overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Enrollment No</TableHead>
                      <TableHead>Student</TableHead>
                      <TableHead>Internal</TableHead>
                      <TableHead>Mid-sem</TableHead>
                      <TableHead>End-sem</TableHead>
                      <TableHead>Total</TableHead>
                      <TableHead>%</TableHead>
                      <TableHead>Grade</TableHead>
                      <TableHead>Result</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Remarks</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {grid.rows.map((row) => {
                      const draft = drafts[row.enrollment_record_id]
                      return (
                        <TableRow key={row.enrollment_record_id}>
                          <TableCell className="font-mono text-xs text-muted-foreground">
                            {String(row.enrollment_no).padStart(3, "0")}
                          </TableCell>
                          <TableCell className="font-medium">
                            {row.first_name} {row.last_name}
                          </TableCell>
                          <TableCell>
                            <Input
                              type="number"
                              inputMode="numeric"
                              min={0}
                              max={config.internal_max}
                              value={fieldDraftValue(row, draft, "internal")}
                              onChange={(event) =>
                                setField(row.enrollment_record_id, "internal", event.target.value)
                              }
                              className="h-8 w-20 text-sm tabular-nums"
                              aria-label={`Internal marks for ${row.first_name} ${row.last_name}`}
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              type="number"
                              inputMode="numeric"
                              min={0}
                              max={config.mid_sem_max}
                              value={fieldDraftValue(row, draft, "mid")}
                              onChange={(event) =>
                                setField(row.enrollment_record_id, "mid", event.target.value)
                              }
                              className="h-8 w-20 text-sm tabular-nums"
                              aria-label={`Mid-sem marks for ${row.first_name} ${row.last_name}`}
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              type="number"
                              inputMode="numeric"
                              min={0}
                              max={config.end_sem_max}
                              value={fieldDraftValue(row, draft, "end")}
                              onChange={(event) =>
                                setField(row.enrollment_record_id, "end", event.target.value)
                              }
                              placeholder="Not entered"
                              className={`h-8 w-20 text-sm tabular-nums ${
                                row.end_sem_marks === null &&
                                (draft?.end === undefined || draft.end === "")
                                  ? "border-dashed border-destructive/40"
                                  : ""
                              }`}
                              aria-label={`End-sem marks for ${row.first_name} ${row.last_name}`}
                            />
                          </TableCell>
                          <TableCell className="font-medium tabular-nums">
                            {row.total_marks !== null ? row.total_marks : "—"}
                          </TableCell>
                          <TableCell className="tabular-nums">
                            {formatPercent(row.percentage)}
                          </TableCell>
                          <TableCell>
                            <GradeBadge grade={row.grade} />
                          </TableCell>
                          <TableCell>
                            {row.result_status ? (
                              <span
                                className={
                                  row.result_status === "Pass"
                                    ? "font-medium text-chart-2"
                                    : "font-medium text-destructive"
                                }
                              >
                                {row.result_status}
                              </span>
                            ) : (
                              "—"
                            )}
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {row.performance_category ?? "—"}
                          </TableCell>
                          <TableCell>
                            <Input
                              type="text"
                              maxLength={config.remarks_max_length}
                              value={fieldDraftValue(row, draft, "remarks")}
                              onChange={(event) =>
                                setField(row.enrollment_record_id, "remarks", event.target.value)
                              }
                              placeholder="Remarks"
                              className="h-8 w-44 text-sm"
                              aria-label={`Remarks for ${row.first_name} ${row.last_name}`}
                            />
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>
            )}

            {grid.pagination.total > grid.pagination.page_size && (
              <p className="text-xs text-muted-foreground">
                Showing {grid.rows.length} of {grid.pagination.total} enrolled students in this
                scope.
              </p>
            )}

            <section
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10"
              aria-label="Save bar"
            >
              <div className="flex min-w-0 flex-col gap-1">
                <p className="text-sm font-medium">
                  {draftCount === 0
                    ? "No unsaved changes"
                    : `${draftCount} row${draftCount === 1 ? "" : "s"} edited`}
                </p>
                {summary ? (
                  <p className="flex items-center gap-1.5 text-sm text-chart-2" role="status">
                    <CheckCircle2 className="size-4 shrink-0" />
                    Saved {summary.saved} of {grid.pagination.total} · {summary.inserted} inserted ·{" "}
                    {summary.updated} updated · {summary.unchanged} unchanged · {summary.rejected}{" "}
                    rejected
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Derived values (Total, %, Grade, Result, Category) refresh after a successful
                    save.
                  </p>
                )}
              </div>
              <Button
                onClick={() => void handleSave()}
                disabled={saving || draftCount === 0}
              >
                {saving ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <Save className="size-4" />
                )}
                {saving ? "Saving…" : "Save marks"}
              </Button>
            </section>
          </div>
        </TabsContent>

        <TabsContent value="history">
          <MarksChangeHistory
            subjectId={subjectId}
            semester={grid.semester_no}
            academicYear={grid.academic_year}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
