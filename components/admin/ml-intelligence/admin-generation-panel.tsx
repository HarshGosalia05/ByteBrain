"use client"

import * as React from "react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  Play,
  Loader2,
  CheckCircle2,
  CircleAlert,
  RefreshCw,
  FlaskConical,
} from "lucide-react"

import type { MlGenerationJobStatus } from "@/lib/admin-api"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const MODEL_LABELS: Record<string, string> = {
  m1: "M1 - Subject Marks",
  m2: "M2 - Next-Sem Performance",
  m3: "M3 v3 - End-Term Risk (Mid-Sem → End-Term)",
  m4: "M4 - Career Readiness (rule-based)",
}


const TERMINAL = new Set(["completed", "failed", "cancelled"])

function statusTone(status: string): string {
  switch (status) {
    case "completed":
      return "bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400"
    case "failed":
      return "bg-red-500/10 text-red-600 border-red-500/20 dark:text-red-400"
    case "running":
    case "queued":
      return "bg-blue-500/10 text-blue-600 border-blue-500/20 dark:text-blue-400"
    default:
      return "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400"
  }
}

export function AdminGenerationPanel() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const filters = React.useMemo(
    () => ({
      department_code: searchParams.get("department_code") ?? "",
      semester: searchParams.get("semester") ?? "",
      batch: searchParams.get("batch") ?? searchParams.get("academic_year") ?? "",
    }),
    [searchParams],
  )

  const [selected, setSelected] = React.useState<Record<string, boolean>>({
    m1: true,
    m2: true,
    m3: true,
    m4: true,
  })
  const [force, setForce] = React.useState(false)
  const [job, setJob] = React.useState<MlGenerationJobStatus | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [starting, setStarting] = React.useState(false)

  const running = job !== null && !TERMINAL.has(job.status)

  // Poll the job until it settles.
  React.useEffect(() => {
    const current = job
    if (!current || !current.job_id || TERMINAL.has(current.status)) return
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/admin/ml-intelligence/generate/status/${current.job_id}`, {
          cache: "no-store",
        })
        const body = await res.json()
        if (body?.ok && body.data) {
          setJob(body.data)
          if (TERMINAL.has(body.data.status)) {
            router.refresh()
          }
        } else if (body?.error) {
          setError(body.error.message ?? "Failed to fetch generation status.")
          setJob((prev) =>
            prev ? { ...prev, status: "failed", error: body.error.message } : prev,
          )
        }
      } catch {
        // transient network errors are ignored; next poll retries
      }
    }, 2500)
    return () => clearInterval(timer)
  }, [job?.job_id, router])

  const startRun = async () => {
    setError(null)
    setStarting(true)
    setJob(null)
    try {
      const qparams = new URLSearchParams()
      if (filters.department_code) qparams.set("department_code", filters.department_code)
      if (filters.semester) qparams.set("semester", filters.semester)
      if (filters.batch) qparams.set("batch", filters.batch)
      const qs = qparams.toString()

      const models = Object.keys(selected).filter((m) => selected[m])
      const res = await fetch(`/api/admin/ml-intelligence/generate${qs ? `?${qs}` : ""}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ models, force }),
        cache: "no-store",
      })
      const body = await res.json()
      if (body?.ok && body.data) {
        setJob({
          job_id: body.data.job_id,
          status: body.data.status === "queued" ? "queued" : body.data.status,
          models: body.data.models,
          force,
          total_tasks: 0,
          completed_tasks: 0,
          failed_tasks: 0,
          skipped_tasks: 0,
          progress_percent: 0,
          per_model: body.data.models.map((m: string) => ({
            model: m,
            eligible: 0,
            total: 0,
            completed: 0,
            failed: 0,
            skipped: 0,
          })),
          department_code: filters.department_code
            ? Number(filters.department_code)
            : null,
          semester: filters.semester ? Number(filters.semester) : null,
          academic_year: filters.batch || null,
          started_at: null,
          finished_at: null,
          errors: [],
        })
      } else {
        setError(body?.error?.message ?? "Failed to start ML generation.")
      }
    } finally {
      setStarting(false)
    }
  }

  const resetPanel = () => {
    setJob(null)
    setError(null)
  }

  const totalCompleted = job?.completed_tasks ?? 0
  const totalTasks = job?.total_tasks ?? 0
  const progress = job?.progress_percent ?? 0

  return (
    <section className="min-w-0 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <FlaskConical className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
          <div>
            <h2 className="text-sm font-semibold">Generate ML Predictions</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Run M1-M4 generation & persistence for students in the current scope.
              Runs asynchronously; you can keep browsing while it completes.
            </p>
          </div>
        </div>
        {job && !running && (
          <Button variant="ghost" size="sm" onClick={resetPanel} className="shrink-0">
            <RefreshCw className="size-3.5" /> Reset
          </Button>
        )}
      </div>

      {error && (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {!running && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {Object.keys(MODEL_LABELS).map((model) => (
              <label key={model} className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={selected[model]}
                  onChange={(e) =>
                    setSelected((prev) => ({ ...prev, [model]: e.target.checked }))
                  }
                  className="size-3.5 accent-primary"
                />
                {MODEL_LABELS[model]}
              </label>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={force}
                onChange={(e) => setForce(e.target.checked)}
                className="size-3.5 accent-primary"
              />
              Force re-generate (overwrite existing predictions)
            </label>
            <Button onClick={startRun} disabled={starting || !Object.values(selected).some(Boolean)}>
              {starting ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Play className="size-4" />
              )}
              {starting ? "Starting…" : "Run Models"}
            </Button>
          </div>
        </div>
      )}

      {job && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
                statusTone(job.status),
              )}
            >
              {running ? (
                <Loader2 className="size-3 animate-spin" />
              ) : job.status === "completed" ? (
                <CheckCircle2 className="size-3" />
              ) : (
                <CircleAlert className="size-3" />
              )}
              Generation {job.status}
            </span>
            {running && totalTasks > 0 && (
              <span className="text-xs text-muted-foreground">
                {totalCompleted} / {totalTasks} tasks
              </span>
            )}
            {!running && (
              <span className="text-xs text-muted-foreground">
                {totalCompleted - job.failed_tasks} succeeded · {job.failed_tasks} failed ·{" "}
                {job.skipped_tasks} skipped
              </span>
            )}
          </div>

          {running && totalTasks > 0 && (
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${Math.min(progress, 100)}%` }}
              />
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            {job.per_model.map((pm) => {
              const tasks = pm.total
              const done = pm.completed + pm.failed
              const pct = tasks > 0 ? Math.round((done / tasks) * 100) : 0
              return (
                <div
                  key={pm.model}
                  className="rounded-lg border border-border/60 px-3 py-2.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold">
                      {MODEL_LABELS[pm.model] ?? pm.model.toUpperCase()}
                    </span>
                    <span className="text-[0.7rem] text-muted-foreground">{pct}%</span>
                  </div>
                  <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-full transition-all",
                        pm.failed > 0 ? "bg-amber-500" : "bg-primary",
                      )}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="mt-1.5 flex gap-2 text-[0.7rem] text-muted-foreground">
                    <span>
                      <span className="font-medium text-emerald-600 dark:text-emerald-400">
                        {pm.completed}
                      </span>{" "}
                      done
                    </span>
                    <span>
                      <span className="font-medium text-red-600 dark:text-red-400">
                        {pm.failed}
                      </span>{" "}
                      failed
                    </span>
                    <span>
                      <span className="font-medium">{pm.skipped}</span> skipped
                    </span>
                    <span className="ml-auto">
                      {pm.eligible} eligible
                    </span>
                  </div>
                </div>
              )
            })}
          </div>

          {job.errors.length > 0 && !running && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2">
              <p className="mb-1 text-xs font-semibold text-amber-600 dark:text-amber-400">
                Sample failures
              </p>
              <ul className="space-y-0.5">
                {job.errors.slice(0, 5).map((e, i) => (
                  <li key={i} className="text-[0.7rem] text-muted-foreground">
                    <span className="font-mono">{e.student_id}</span> · {e.model} · {e.error}
                  </li>
                ))}
              </ul>
              {job.errors.length > 5 && (
                <p className="mt-1 text-[0.7rem] text-muted-foreground">
                  … and {job.errors.length - 5} more
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  )
}