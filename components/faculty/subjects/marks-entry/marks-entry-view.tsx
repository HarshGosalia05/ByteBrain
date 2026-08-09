"use client"

import * as React from "react"
import Link from "next/link"
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardList,
  Eraser,
  Eye,
  EyeOff,
  LoaderCircle,
  RefreshCw,
  Save,
  TriangleAlert,
  Undo2,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
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

const ACTIONS_VISIBLE_KEY = "faculty_marks_actions_visible"

type CellDraftValue = string | null

type CellDraft = {
  internal?: CellDraftValue
  mid?: CellDraftValue
  end?: CellDraftValue
}

type MarkField = "internal" | "mid" | "end"

const MARK_FIELDS: MarkField[] = ["internal", "mid", "end"]

type EditableFieldKey = keyof CellDraft

const EDITABLE_FIELDS: Array<{
  key: EditableFieldKey
  apiField: "internal_marks" | "mid_sem_marks" | "end_sem_marks"
  label: string
  clearLabel: string
}> = [
  { key: "internal", apiField: "internal_marks", label: "Internal", clearLabel: "Internal Marks" },
  { key: "mid", apiField: "mid_sem_marks", label: "Mid-sem", clearLabel: "Mid-sem Marks" },
  { key: "end", apiField: "end_sem_marks", label: "End-sem", clearLabel: "End-sem Marks" },
]

const ROW_KEY: Record<keyof CellDraft, "internal_marks" | "mid_sem_marks" | "end_sem_marks"> = {
  internal: "internal_marks",
  mid: "mid_sem_marks",
  end: "end_sem_marks",
}

type FieldIssue = {
  enrollment_record_id: string
  student_name: string
  field_label: string
  message: string
}

type FieldErrorMap = Partial<Record<MarkField, string>>

type Notice =
  | { kind: "success"; title: string; detail?: string }
  | { kind: "error"; title: string; detail?: string }

type ClearTarget = {
  enrollmentRecordId: string
  fieldKey: EditableFieldKey
  apiField: (typeof EDITABLE_FIELDS)[number]["apiField"]
  label: string
  value: number | string
  studentName: string
}

// Live preview of the derived academic fields. It mirrors the authoritative
// server derivation (faculty_service.derive_marks_fields) using the
// server-provided config bands, so the client never invents its own rules.
// Derived fields are ONLY computed when all three marks are present.
type LiveDerived = {
  complete: boolean
  total: number | null
  percentage: number | null
  grade: string | null
  gradePoint: number | null
  resultStatus: string | null
  category: string | null
  remark: string | null
}

const INCOMPLETE_DERIVED: LiveDerived = {
  complete: false,
  total: null,
  percentage: null,
  grade: null,
  gradePoint: null,
  resultStatus: null,
  category: null,
  remark: null,
}

function computeLiveDerived(
  config: SubjectMarksGrid["config"],
  internal: number | null,
  mid: number | null,
  end: number | null,
): LiveDerived {
  if (internal === null || mid === null || end === null) {
    return INCOMPLETE_DERIVED
  }
  const total = internal + mid + end
  const pct = (total / config.total_max) * 100
  const percentage = Math.round(pct * 100) / 100

  let grade: string | null = null
  let gradePoint: number | null = null
  for (const band of config.grade_bands) {
    if (percentage >= band.min_percentage) {
      grade = band.grade
      gradePoint = band.grade_point
      break
    }
  }
  if (grade === null) {
    grade = "F"
    gradePoint = 0
  }

  let category: string | null = "Low Performer"
  for (const band of config.category_bands) {
    if (percentage >= band.min_percentage) {
      category = band.category
      break
    }
  }

  let remark: string | null = "At risk - improvement required"
  for (const band of config.remark_bands ?? []) {
    if (percentage >= band.min_percentage) {
      remark = band.remark
      break
    }
  }

  return {
    complete: true,
    total,
    percentage,
    grade,
    gradePoint,
    resultStatus: percentage >= config.pass_percentage ? "Pass" : "Fail",
    category,
    remark,
  }
}

function parseNumber(text: string | undefined): number | null | "invalid" {
  if (text === undefined || text.trim() === "") return null
  const parsed = Number(text)
  if (!Number.isFinite(parsed)) return "invalid"
  return parsed
}

function marksFieldMax(config: SubjectMarksGrid["config"], field: MarkField): number {
  if (field === "internal") return config.internal_max
  if (field === "mid") return config.mid_sem_max
  return config.end_sem_max
}

function validateMarksField(raw: string, max: number): string | null {
  const trimmed = raw.trim()
  if (trimmed === "") return null
  const parsed = Number(trimmed)
  if (!Number.isFinite(parsed)) return "must be a valid number."
  if (!Number.isInteger(parsed)) return "must be a whole number."
  if (parsed < 0 || parsed > max) return `must be between 0 and ${max}.`
  return null
}

function formatPercent(value: number | null): string {
  return value !== null ? `${value.toFixed(1)}%` : "—"
}

function fieldDraftValue(
  row: SubjectMarksRow,
  draft: CellDraft | undefined,
  field: keyof CellDraft,
): string {
  if (draft && draft[field] !== undefined) {
    return draft[field] === null ? "" : draft[field]
  }
  const value = row[ROW_KEY[field]]
  return value === null || value === undefined ? "" : String(value)
}

function effectiveFieldValue(
  row: SubjectMarksRow,
  draft: CellDraft | undefined,
  field: keyof CellDraft,
): string | number | null {
  if (draft && draft[field] !== undefined) return draft[field]
  const value = row[ROW_KEY[field]]
  return value === null || value === undefined ? null : value
}

function effectiveMarks(
  row: SubjectMarksRow,
  draft: CellDraft | undefined,
): { internal: number | null; mid: number | null; end: number | null } {
  const parse = (field: MarkField): number | null => {
    const effective = effectiveFieldValue(row, draft, field)
    if (effective === null || effective === "") return null
    if (typeof effective === "number") return effective
    const parsed = Number(effective)
    return Number.isFinite(parsed) ? parsed : null
  }
  return { internal: parse("internal"), mid: parse("mid"), end: parse("end") }
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
  const [clearing, setClearing] = React.useState(false)
  const [clearTarget, setClearTarget] = React.useState<ClearTarget | null>(null)
  const [notice, setNotice] = React.useState<Notice | null>(null)
  const [summary, setSummary] = React.useState<MarksBatchSaveResponse["summary"] | null>(null)
  const [loadError, setLoadError] = React.useState<string | null>(null)
  const [actionsVisible, setActionsVisible] = React.useState(true)
  const noticeTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  function showNotice(next: Notice, ttlMs: number) {
    setNotice(next)
    if (noticeTimer.current) clearTimeout(noticeTimer.current)
    noticeTimer.current = setTimeout(() => setNotice(null), ttlMs)
  }

  function clearNotice() {
    if (noticeTimer.current) clearTimeout(noticeTimer.current)
    noticeTimer.current = null
    setNotice(null)
  }

  React.useEffect(() => {
    return () => {
      if (noticeTimer.current) clearTimeout(noticeTimer.current)
    }
  }, [])

  // Actions column visibility preference. Local UI preference only - never a
  // database value. The default is "visible"; the stored preference is applied
  // after mount so the server and first client render stay identical (no
  // hydration mismatch).
  React.useEffect(() => {
    try {
      const stored = window.localStorage.getItem(ACTIONS_VISIBLE_KEY)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (stored !== null) setActionsVisible(stored === "1")
    } catch {
      // Storage unavailable (private mode etc.) - keep the default.
    }
  }, [])

  React.useEffect(() => {
    try {
      window.localStorage.setItem(ACTIONS_VISIBLE_KEY, actionsVisible ? "1" : "0")
    } catch {
      // Storage unavailable - preference simply is not persisted.
    }
  }, [actionsVisible])

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
      const studentName = `${row.first_name} ${row.last_name}`
      const specs: Array<[MarkField, string]> = [
        ["internal", "Internal"],
        ["mid", "Mid-sem"],
        ["end", "End-sem"],
      ]
      for (const [field, label] of specs) {
        const raw = draft[field]
        if (raw === undefined || raw === null) continue
        const message = validateMarksField(raw, marksFieldMax(config, field))
        if (message) {
          issues.push({
            enrollment_record_id: enrollmentRecordId,
            student_name: studentName,
            field_label: label,
            message,
          })
        }
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
      clearNotice()
    } catch {
      setLoadError("Could not refresh the marks grid. Please try again.")
    } finally {
      setRefreshing(false)
    }
  }

  async function handleSave() {
    if (saving) return
    const issues = validateDrafts()
    if (issues.length > 0) {
      showNotice(
        {
          kind: "error",
          title: "Cannot save marks",
          detail: `Fix ${issues.length} field issue${issues.length === 1 ? "" : "s"} highlighted in the grid before saving.`,
        },
        6000,
      )
      return
    }
    const rows: MarksRowInput[] = Object.entries(drafts).map(
      ([enrollmentRecordId, draft]) => {
        const row: MarksRowInput = { enrollment_record_id: enrollmentRecordId }
        if (draft.internal !== undefined) {
          row.internal_marks =
            draft.internal === null ? null : (parseNumber(draft.internal) as number | null)
        }
        if (draft.mid !== undefined) {
          row.mid_sem_marks =
            draft.mid === null ? null : (parseNumber(draft.mid) as number | null)
        }
        if (draft.end !== undefined) {
          row.end_sem_marks =
            draft.end === null ? null : (parseNumber(draft.end) as number | null)
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
    clearNotice()
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
        if (result.error.status === 422) {
          showNotice(
            {
              kind: "error",
              title: "Could not save marks",
              detail:
                "One or more values are outside the allowed range (Internal: 0–20 · Mid-sem: 0–50 · End-sem: 0–70). Check the highlighted fields and try again.",
            },
            6000,
          )
        } else {
          showNotice(
            {
              kind: "error",
              title: "Could not save marks",
              detail: result.error.message,
            },
            6000,
          )
        }
        return
      }
      setGrid(result.data.grid)
      setFetchedAt(result.fetchedAt)
      setSummary(result.data.summary)
      setDrafts({})
      showNotice(
        {
          kind: "success",
          title: "Marks saved successfully.",
          detail: `${result.data.summary.updated} updated · ${result.data.summary.inserted} inserted · ${result.data.summary.rejected} rejected`,
        },
        4000,
      )
    } catch {
      showNotice(
        {
          kind: "error",
          title: "Could not save marks",
          detail: "Please check your connection and try again.",
        },
        6000,
      )
    } finally {
      setSaving(false)
    }
  }

  function onClearRequest(row: SubjectMarksRow, fieldKey: EditableFieldKey) {
    const draftValue = drafts[row.enrollment_record_id]?.[fieldKey]
    if (draftValue !== undefined && draftValue !== null) {
      // Newly typed, unsaved value: remove the draft without confirmation.
      setField(row.enrollment_record_id, fieldKey, "")
      return
    }
    const apiField = ROW_KEY[fieldKey]
    const saved = row[apiField]
    if (saved === null || saved === undefined) return
    const spec = EDITABLE_FIELDS.find((f) => f.key === fieldKey)
    if (!spec) return
    setClearTarget({
      enrollmentRecordId: row.enrollment_record_id,
      fieldKey,
      apiField: spec.apiField,
      label: spec.label,
      value: saved,
      studentName: `${row.first_name} ${row.last_name}`,
    })
  }

  async function confirmClear() {
    if (!clearTarget || clearing) return
    const { enrollmentRecordId, apiField, label } = clearTarget
    setClearing(true)
    try {
      const row: MarksRowInput = { enrollment_record_id: enrollmentRecordId }
      if (apiField === "internal_marks") row.internal_marks = null
      else if (apiField === "mid_sem_marks") row.mid_sem_marks = null
      else if (apiField === "end_sem_marks") row.end_sem_marks = null

      const payload: MarksBatchSaveRequest = {
        semester_no: grid.semester_no,
        academic_year: grid.academic_year,
        rows: [row],
      }
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
        showNotice(
          {
            kind: "error",
            title: "Could not clear field",
            detail: result.error.message,
          },
          6000,
        )
        return
      }
      setGrid(result.data.grid)
      setFetchedAt(result.fetchedAt)
      setSummary(null)
      showNotice(
        {
          kind: "success",
          title: `${label} marks cleared successfully.`,
        },
        4000,
      )
    } catch {
      showNotice(
        {
          kind: "error",
          title: "Could not clear field",
          detail: "Please check your connection and try again.",
        },
        6000,
      )
    } finally {
      setClearing(false)
      setClearTarget(null)
    }
  }

  const issues = validateDrafts()

  const fieldErrors = React.useMemo(() => {
    const map: Record<string, FieldErrorMap> = {}
    for (const [enrollmentRecordId, draft] of Object.entries(drafts)) {
      for (const field of MARK_FIELDS) {
        const raw = draft[field]
        if (raw === undefined || raw === null) continue
        const message = validateMarksField(raw, marksFieldMax(config, field))
        if (message) {
          map[enrollmentRecordId] = { ...map[enrollmentRecordId], [field]: message }
        }
      }
    }
    return map
  }, [drafts, config])

  // Live preview of derived values. When any field on a row is invalid the
  // preview stays "not calculated" (no partial/incorrect derivation).
  function liveDerivedForRow(row: SubjectMarksRow): LiveDerived {
    const errors = fieldErrors[row.enrollment_record_id]
    if (errors && Object.keys(errors).length > 0) return INCOMPLETE_DERIVED
    const marks = effectiveMarks(row, drafts[row.enrollment_record_id])
    return computeLiveDerived(config, marks.internal, marks.mid, marks.end)
  }

  function marksInputFor(row: SubjectMarksRow, field: MarkField) {
    const max = marksFieldMax(config, field)
    const error = fieldErrors[row.enrollment_record_id]?.[field]
    const effective = effectiveFieldValue(row, drafts[row.enrollment_record_id], field)
    const empty = effective === null || effective === ""
    return (
      <div className="flex min-w-0 flex-col gap-1">
        <Input
          type="number"
          inputMode="numeric"
          min={0}
          max={max}
          placeholder="Not entered"
          value={fieldDraftValue(row, drafts[row.enrollment_record_id], field)}
          onChange={(event) => setField(row.enrollment_record_id, field, event.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={
            error ? `${row.enrollment_record_id}-${field}-error` : undefined
          }
          className={cn(
            "h-8 w-full text-sm tabular-nums",
            error
              ? "border-destructive focus-visible:ring-destructive/40"
              : field === "end" && empty
                ? "border-dashed border-destructive/40"
                : "",
          )}
          aria-label={`${field === "internal" ? "Internal" : field === "mid" ? "Mid-sem" : "End-sem"} marks for ${row.first_name} ${row.last_name}`}
        />
        {error ? (
          <p
            id={`${row.enrollment_record_id}-${field}-error`}
            className="w-full text-[11px] leading-tight text-destructive"
          >
            {error}
          </p>
        ) : null}
      </div>
    )
  }

  // Per-field action buttons. Two genuine behaviours:
  //  * an unsaved draft -> "Reset" (Undo2) restores the saved database value by
  //    discarding only that field's draft, immediately updating the UI;
  //  * a saved value -> "Clear" (Eraser) sets the field to NULL through the
  //    existing save path (backend stays authoritative, change history records
  //    the clear). Clearing never touches other marks or other students.
  function fieldActionButton(row: SubjectMarksRow, field: MarkField) {
    const draftValue = drafts[row.enrollment_record_id]?.[field]
    const isDraft = draftValue !== undefined
    const savedValue = row[ROW_KEY[field]]
    const hasValue = isDraft
      ? draftValue !== null && draftValue !== ""
      : savedValue !== null && savedValue !== undefined
    if (!hasValue) return null
    const spec = EDITABLE_FIELDS.find((f) => f.key === field)
    const label = spec?.label ?? field
    const studentName = `${row.first_name} ${row.last_name}`
    if (isDraft) {
      return (
        <Button
          key={`${row.enrollment_record_id}-${field}-reset`}
          variant="ghost"
          size="icon-xs"
          onClick={() => setField(row.enrollment_record_id, field, "")}
          title={`Reset ${label} to its saved value`}
          aria-label={`Reset ${label} for ${studentName} to its saved value`}
        >
          <Undo2 />
        </Button>
      )
    }
    return (
      <Button
        key={`${row.enrollment_record_id}-${field}-clear`}
        variant="ghost"
        size="icon-xs"
        className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive focus-visible:ring-destructive/30"
        onClick={() => onClearRequest(row, field)}
        title={`Clear ${label}`}
        aria-label={`Clear ${label} for ${studentName}`}
      >
        <Eraser />
      </Button>
    )
  }

  function remarksValue(live: LiveDerived): string {
    // Automatic academic remark derived from percentage via the server-provided
    // remark bands (single source of truth). Incomplete marks -> no remark, and
    // the database value stays NULL; the UI shows "Not available yet".
    return live.complete ? (live.remark ?? "Not available yet") : "Not available yet"
  }

  function derivedChips(row: SubjectMarksRow, live: LiveDerived) {
    return (
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <Badge variant="muted">
          Total {live.complete && live.total !== null ? live.total : "Not Calculated"}
        </Badge>
        <Badge variant="muted">
          % {live.complete && live.percentage !== null ? formatPercent(live.percentage) : "Not Calculated"}
        </Badge>
        <Badge variant="muted">
          Grade {live.complete && live.grade ? live.grade : "—"}
        </Badge>
        <Badge
          variant={
            live.complete && live.resultStatus
              ? live.resultStatus === "Pass"
                ? "success"
                : "destructive"
              : "muted"
          }
        >
          {live.complete && live.resultStatus ? live.resultStatus : "—"}
        </Badge>
        <Badge variant="muted">
          {live.complete ? (live.category ?? "—") : "—"}
        </Badge>
      </div>
    )
  }

  const actionsToggle = (
    <Button
      variant="outline"
      size="sm"
      onClick={() => setActionsVisible((value) => !value)}
      aria-pressed={actionsVisible}
      title={actionsVisible ? "Hide Actions column" : "Show Actions column"}
      aria-label={actionsVisible ? "Hide Actions column" : "Show Actions column"}
    >
      {actionsVisible ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
      Actions
    </Button>
  )

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
            {actionsToggle}
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
            {item.label} /{item.max}
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
            {notice && (
              <section
                className={`flex flex-wrap items-start gap-3 rounded-xl border p-4 ${
                  notice.kind === "success"
                    ? "border-chart-2/30 bg-chart-2/5"
                    : "border-destructive/30 bg-destructive/5"
                }`}
                role={notice.kind === "success" ? "status" : "alert"}
                aria-live="polite"
              >
                {notice.kind === "success" ? (
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-chart-2" />
                ) : (
                  <TriangleAlert className="mt-0.5 size-4 shrink-0 text-destructive" />
                )}
                <div className="min-w-0 flex-1">
                  <p
                    className={`text-sm font-medium ${
                      notice.kind === "success" ? "text-chart-2" : "text-destructive"
                    }`}
                  >
                    {notice.title}
                  </p>
                  {notice.detail ? (
                    <p className="mt-0.5 text-sm text-muted-foreground">{notice.detail}</p>
                  ) : null}
                </div>
              </section>
            )}

            {issues.length > 0 && (
              <section
                className="rounded-xl border border-destructive/30 bg-destructive/5 p-4"
                role="alert"
              >
                <div className="flex items-center gap-2">
                  <TriangleAlert className="size-4 text-destructive" />
                  <p className="text-sm font-medium text-destructive">
                    Fix the following before saving ({issues.length}):
                  </p>
                </div>
                <ul className="mt-2 flex max-h-48 flex-col gap-1 overflow-y-auto pr-1 text-sm text-muted-foreground">
                  {issues.map((issue, index) => (
                    <li key={`${issue.enrollment_record_id}-${index}`} className="min-w-0">
                      <span className="font-medium text-foreground">{issue.student_name}</span>
                      {" — "}
                      {issue.field_label}: {issue.message}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {grid.rows.length === 0 ? (
              <EmptyState
                icon={ClipboardList}
                title="No marks to display"
                description="No enrollment rows are available in this subject and term scope."
              />
            ) : (
              <>
                <div className="hidden overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10 xl:block">
                  <Table
                    className={cn(
                      "table-fixed w-full",
                      actionsVisible ? "min-w-[1000px]" : "min-w-[936px]",
                    )}
                  >
                    <TableHeader>
                      <TableRow>
                        <TableHead className="sticky left-0 z-20 w-14 bg-card">
                          Enrollment No
                        </TableHead>
                        <TableHead className="sticky left-14 z-20 w-32 bg-card">
                          Student Name
                        </TableHead>
                        <TableHead className="w-20">Internal</TableHead>
                        <TableHead className="w-20">Mid-sem</TableHead>
                        <TableHead className="w-20">End-sem</TableHead>
                        <TableHead className="w-14">Total</TableHead>
                        <TableHead className="w-16">%</TableHead>
                        <TableHead className="w-14">Grade</TableHead>
                        <TableHead className="w-16">Result</TableHead>
                        <TableHead className="w-24">Category</TableHead>
                        <TableHead className="w-44">Remarks</TableHead>
                        {actionsVisible ? (
                          <TableHead className="w-16">Actions</TableHead>
                        ) : null}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {grid.rows.map((row) => {
                        const live = liveDerivedForRow(row)
                        return (
                          <TableRow key={row.enrollment_record_id}>
                            <TableCell className="sticky left-0 z-10 w-14 bg-card font-mono text-xs text-muted-foreground">
                              {String(row.enrollment_no).padStart(3, "0")}
                            </TableCell>
                            <TableCell className="sticky left-14 z-10 w-32 bg-card font-medium">
                              <span className="block break-words">
                                {row.first_name} {row.last_name}
                              </span>
                            </TableCell>
                            <TableCell className="w-20">
                              {marksInputFor(row, "internal")}
                            </TableCell>
                            <TableCell className="w-20">
                              {marksInputFor(row, "mid")}
                            </TableCell>
                            <TableCell className="w-20">
                              {marksInputFor(row, "end")}
                            </TableCell>
                            <TableCell className="w-14 font-medium tabular-nums">
                              {live.complete && live.total !== null ? (
                                live.total
                              ) : (
                                <span className="whitespace-normal break-words italic text-muted-foreground">
                                  Not Calculated
                                </span>
                              )}
                            </TableCell>
                            <TableCell className="w-16 tabular-nums">
                              {live.complete && live.percentage !== null ? (
                                formatPercent(live.percentage)
                              ) : (
                                <span className="whitespace-normal break-words italic text-muted-foreground">
                                  Not Calculated
                                </span>
                              )}
                            </TableCell>
                            <TableCell className="w-14">
                              {live.complete && live.grade ? (
                                <GradeBadge grade={live.grade} />
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </TableCell>
                            <TableCell className="w-16">
                              {live.complete && live.resultStatus ? (
                                <span
                                  className={
                                    live.resultStatus === "Pass"
                                      ? "font-medium text-chart-2"
                                      : "font-medium text-destructive"
                                  }
                                >
                                  {live.resultStatus}
                                </span>
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </TableCell>
                            <TableCell className="w-24 break-words text-muted-foreground">
                              {live.complete ? (live.category ?? "—") : "—"}
                            </TableCell>
                            <TableCell className="w-44">
                              <span
                                className={cn(
                                  "block break-words text-sm",
                                  live.complete ? "font-medium text-foreground" : "text-muted-foreground",
                                )}
                              >
                                {remarksValue(live)}
                              </span>
                            </TableCell>
                            {actionsVisible ? (
                              <TableCell className="w-16 align-top">
                                <div className="flex flex-wrap items-center gap-1">
                                  {MARK_FIELDS.map((field) => fieldActionButton(row, field))}
                                </div>
                              </TableCell>
                            ) : null}
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>

                <div className="flex flex-col gap-3 xl:hidden">
                  {grid.rows.map((row) => {
                    const live = liveDerivedForRow(row)
                    return (
                      <div
                        key={row.enrollment_record_id}
                        className="flex flex-col gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-mono text-xs text-muted-foreground">
                              {String(row.enrollment_no).padStart(3, "0")}
                            </p>
                            <p className="mt-0.5 font-medium">
                              {row.first_name} {row.last_name}
                            </p>
                          </div>
                          {derivedChips(row, live)}
                        </div>
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                          {EDITABLE_FIELDS.map((spec) => (
                            <div key={spec.key} className="flex min-w-0 flex-col gap-1">
                              <div className="flex items-center justify-between gap-1">
                                <span className="text-xs font-medium text-muted-foreground">
                                  {spec.label}
                                </span>
                                {actionsVisible
                                  ? fieldActionButton(row, spec.key as MarkField)
                                  : null}
                              </div>
                              {marksInputFor(row, spec.key as MarkField)}
                            </div>
                          ))}
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="text-xs font-medium text-muted-foreground">
                            Remarks
                          </span>
                          <span
                            className={cn(
                              "break-words text-sm",
                              live.complete
                                ? "font-medium text-foreground"
                                : "text-muted-foreground",
                            )}
                          >
                            {remarksValue(live)}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
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
                    Derived values (Total, %, Grade, Result, Category, Remarks) preview as you type
                    and are confirmed by the server when you save.
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

      <Dialog
        open={clearTarget !== null}
        onOpenChange={(open) => {
          if (!open && !clearing) setClearTarget(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear {clearTarget?.label ?? ""} marks?</DialogTitle>
            <DialogDescription>
              {clearTarget?.value} marks will be removed for {clearTarget?.studentName}. This
              cannot be undone from this screen.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={clearing}
              onClick={() => setClearTarget(null)}
            >
              Cancel
            </Button>
            <Button variant="destructive" disabled={clearing} onClick={() => void confirmClear()}>
              {clearing ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Eraser className="size-4" />
              )}
              {clearing ? "Clearing…" : "Clear Mark"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
