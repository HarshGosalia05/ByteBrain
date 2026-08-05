"use client"

import * as React from "react"
import { ArchiveRestore, CheckCircle2, Download, HardDriveUpload, History, TriangleAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { FacultySettingsResponse } from "@/lib/faculty-api"

import { PreferenceSection } from "./preference-section"
import { ResetDialog } from "./reset-dialog"

type Notice = { kind: "ok" | "error"; text: string } | null

export function WorkspaceManagement({ settings }: { settings: FacultySettingsResponse }) {
  const [busy, setBusy] = React.useState<string | null>(null)
  const [notice, setNotice] = React.useState<Notice>(null)
  const timer = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const fileRef = React.useRef<HTMLInputElement>(null)

  const restorePoint = settings.metadata.restore_point
  const hasRestorePoint =
    restorePoint != null && typeof restorePoint === "object" && "namespaces" in restorePoint
  const restorePointAt =
    restorePoint != null && typeof restorePoint === "object" && "created_at" in restorePoint
      ? String(restorePoint.created_at)
      : null

  React.useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [])

  function showNotice(kind: "ok" | "error", text: string) {
    setNotice({ kind, text })
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setNotice(null), 5000)
  }

  async function downloadBackup() {
    setBusy("download")
    try {
      const res = await fetch("/api/faculty/settings/workspace/backup", { cache: "no-store" })
      const result = (await res.json()) as
        | { ok: true; data: FacultySettingsBackupData }
        | { ok: false; error: { message: string } }
      if (!result.ok) throw new Error(result.error.message)
      const blob = new Blob([JSON.stringify(result.data, null, 2)], {
        type: "application/json",
      })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `faculty-workspace-backup-${(result.data.exported_at ?? "").slice(0, 10) || "preferences"}.json`
      anchor.click()
      URL.revokeObjectURL(url)
      showNotice("ok", "Configuration backup downloaded.")
    } catch (error) {
      showNotice(
        "error",
        error instanceof Error ? error.message : "Could not download the backup.",
      )
    } finally {
      setBusy(null)
    }
  }

  async function importBackup(file: File) {
    setBusy("import")
    try {
      const text = await file.text()
      const parsed: unknown = JSON.parse(text)
      if (!parsed || typeof parsed !== "object") {
        throw new Error("The selected file is not a valid configuration backup.")
      }
      const record = parsed as Record<string, unknown>
      const source =
        record.namespaces && typeof record.namespaces === "object" && !Array.isArray(record.namespaces)
          ? record.namespaces
          : record
      const res = await fetch("/api/faculty/settings/workspace/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload: source }),
        cache: "no-store",
      })
      const result = (await res.json()) as
        | { ok: true }
        | { ok: false; error: { message: string } }
      if (!result.ok) throw new Error(result.error.message)
      window.location.reload()
    } catch (error) {
      showNotice(
        "error",
        error instanceof Error ? error.message : "Could not import the configuration.",
      )
      setBusy(null)
    }
  }

  async function restoreVersion() {
    if (!hasRestorePoint) return
    setBusy("restore")
    try {
      const res = await fetch("/api/faculty/settings/workspace/restore", {
        method: "POST",
        cache: "no-store",
      })
      const result = (await res.json()) as
        | { ok: true }
        | { ok: false; error: { message: string } }
      if (!result.ok) throw new Error(result.error.message)
      window.location.reload()
    } catch (error) {
      showNotice(
        "error",
        error instanceof Error ? error.message : "Could not restore the configuration.",
      )
      setBusy(null)
    }
  }

  return (
    <PreferenceSection
      icon={ArchiveRestore}
      title="Workspace management"
      description="Back up, import and restore your preference-only workspace configuration. No academic data is ever included."
    >
      <div className="flex flex-col gap-4">
        {notice && (
          <p
            role={notice.kind === "error" ? "alert" : "status"}
            className={`flex items-center gap-1.5 text-sm ${
              notice.kind === "error" ? "text-destructive" : "text-chart-2"
            }`}
          >
            {notice.kind === "error" ? (
              <TriangleAlert className="size-4 shrink-0" />
            ) : (
              <CheckCircle2 className="size-4 shrink-0" />
            )}
            {notice.text}
          </p>
        )}

        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          <Button variant="outline" disabled={busy !== null} onClick={downloadBackup}>
            <Download />
            Download backup
          </Button>
          <Button
            variant="outline"
            disabled={busy !== null}
            onClick={() => fileRef.current?.click()}
          >
            <HardDriveUpload />
            Import configuration
          </Button>
          <Button
            variant="outline"
            disabled={busy !== null || !hasRestorePoint}
            onClick={restoreVersion}
            title={hasRestorePoint ? undefined : "No restore point available yet"}
          >
            <History />
            Restore previous version
          </Button>
        </div>

        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) void importBackup(file)
            event.target.value = ""
          }}
        />

        <p className="text-xs text-muted-foreground">
          {hasRestorePoint && restorePointAt
            ? `A restore point from ${restorePointAt} is available.`
            : "No restore point is available yet. A reset or import creates one automatically."}
        </p>

        <div className="border-t border-border/60 pt-4">
          <ResetDialog />
        </div>
      </div>
    </PreferenceSection>
  )
}

type FacultySettingsBackupData = {
  schema_version?: number
  preference_version?: number
  configuration_version?: number
  exported_at?: string
  namespaces: Record<string, unknown>
}
