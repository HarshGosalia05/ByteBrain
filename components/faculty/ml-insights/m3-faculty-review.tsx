"use client"

import { useEffect, useState } from "react"
import { CheckCircle2, ClipboardCheck, Loader2, RefreshCw, XCircle } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import {
  fetchPredictionFeedbackContextAction,
  submitPredictionFeedbackAction,
} from "@/app/faculty/students/[studentId]/ml-insights/actions"
import type { FacultyFeedbackAction, FacultyStudentFeedbackContext } from "@/lib/faculty-api"

function VerdictBadge({ verdict }: { verdict: FacultyStudentFeedbackContext["current_verdict"] }) {
  if (!verdict) {
    return (
      <Badge variant="muted">
        <ClipboardCheck aria-hidden="true" />
        Pending review
      </Badge>
    )
  }
  if (verdict.feedback_action === "confirmed") {
    return (
      <Badge variant="success">
        <CheckCircle2 aria-hidden="true" />
        Confirmed
      </Badge>
    )
  }
  return (
    <Badge variant="destructive">
      <XCircle aria-hidden="true" />
      Dismissed
    </Badge>
  )
}

export function M3FacultyReview({ studentId }: { studentId: string }) {
  const [mounted, setMounted] = useState(false)
  const [context, setContext] = useState<FacultyStudentFeedbackContext | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState<FacultyFeedbackAction | null>(null)
  const [note, setNote] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  async function loadData() {
    setLoading(true)
    setError(null)
    const result = await fetchPredictionFeedbackContextAction(studentId)
    setLoading(false)
    if (result.ok) {
      setContext(result.data)
      setLoadError(null)
    } else {
      setLoadError(result.error.message)
    }
  }

  useEffect(() => {
    setMounted(true)
    let cancelled = false
    setLoading(true)
    fetchPredictionFeedbackContextAction(studentId).then((result) => {
      if (cancelled) return
      setLoading(false)
      if (result.ok) {
        setContext(result.data)
        setLoadError(null)
      } else {
        setLoadError(result.error.message)
      }
    })
    return () => {
      cancelled = true
    }
  }, [studentId])

  async function submit(action: FacultyFeedbackAction) {
    const predictionId = context?.latest_m3_prediction?.prediction_id
    if (!predictionId) return
    setSubmitting(action)
    setError(null)
    const result = await submitPredictionFeedbackAction(
      predictionId,
      { action, note: note.trim() === "" ? null : note.trim() },
      studentId,
    )
    setSubmitting(null)
    if (result.ok) {
      setNote("")
      await loadData()
    } else {
      setError(result.error.message)
    }
  }

  if (!mounted || loading) {
    return (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-8 w-full" />
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-start gap-2">
        <p className="text-sm text-muted-foreground">{loadError}</p>
        <Button variant="ghost" size="sm" onClick={() => loadData()}>
          <RefreshCw className="size-3.5" aria-hidden="true" />
          Retry
        </Button>
      </div>
    )
  }

  if (!context?.latest_m3_prediction) {
    return (
      <p className="text-sm text-muted-foreground">
        No future-risk prediction has been recorded yet, so there is nothing to review.
      </p>
    )
  }

  const verdict = context.current_verdict

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-muted/30 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-col gap-1">
          <p className="text-[0.6875rem] font-semibold tracking-widest text-muted-foreground uppercase">
            Faculty review
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <VerdictBadge verdict={verdict} />
            {context.latest_m3_prediction.model_version && (
              <span className="text-xs text-muted-foreground">
                model v{context.latest_m3_prediction.model_version}
              </span>
            )}
          </div>
        </div>
      </div>

      {verdict?.note && (
        <p className="rounded-md bg-background px-3 py-2 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Review note: </span>
          {verdict.note}
        </p>
      )}

      <div className="flex flex-col gap-2">
        <label
          htmlFor="ml-12-review-note"
          className="text-xs font-medium text-muted-foreground"
        >
          Add context (optional)
        </label>
        <Textarea
          id="ml-12-review-note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="e.g. I spoke with the student; support is already in place."
          maxLength={2000}
          disabled={submitting !== null}
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex flex-wrap gap-2">
        <Button
          variant={verdict?.feedback_action === "confirmed" ? "default" : "outline"}
          size="sm"
          disabled={submitting !== null}
          onClick={() => submit("confirmed")}
        >
          {submitting === "confirmed" && <Loader2 className="animate-spin" aria-hidden="true" />}
          {verdict?.feedback_action === "confirmed" ? "Confirmed" : "Confirm"}
        </Button>
        <Button
          variant={verdict?.feedback_action === "dismissed" ? "destructive" : "outline"}
          size="sm"
          disabled={submitting !== null}
          onClick={() => submit("dismissed")}
        >
          {submitting === "dismissed" && <Loader2 className="animate-spin" aria-hidden="true" />}
          {verdict?.feedback_action === "dismissed" ? "Dismissed" : "Dismiss"}
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        Your review is stored for model improvement only. It never changes the original
        prediction or the deterministic risk register.
      </p>
    </div>
  )
}
