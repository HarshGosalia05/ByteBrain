"use client"

import * as React from "react"
import { RotateCcw, TriangleAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

import { SelectField } from "./settings-controls"

const RESET_OPTIONS = [
  { value: "dashboard", label: "Reset Dashboard" },
  { value: "analytics", label: "Reset Analytics" },
  { value: "notifications", label: "Reset Notifications" },
  { value: "accessibility", label: "Reset Accessibility" },
  { value: "workspace", label: "Reset Workspace" },
  { value: "factory", label: "Factory Reset Preferences" },
]

const RESET_SCOPE: Record<string, string> = {
  dashboard:
    "Restores landing page, term, compare and chart defaults, favourites and widget configuration. Profile, analytics, notifications, accessibility and export are not touched.",
  analytics:
    "Restores threshold overrides and chart, table and refresh preferences. All other namespaces are not touched.",
  notifications:
    "Restores alert rules, quiet hours, do-not-disturb and digest frequency. All other namespaces are not touched.",
  accessibility:
    "Restores contrast, palette, fonts, motion, focus and presets. All other namespaces are not touched.",
  workspace:
    "Restores layout, density, sidebar, sticky filters, page size and saved workspaces. All other namespaces are not touched.",
  factory:
    "Restores every preference namespace to its role default. Profile-extension fields are retained unless explicitly included below.",
}

export function ResetDialog() {
  const [level, setLevel] = React.useState("workspace")
  const [includeProfileExtra, setIncludeProfileExtra] = React.useState(false)
  const [open, setOpen] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  async function confirmReset() {
    setBusy(true)
    setError(null)
    try {
      const res = await fetch("/api/faculty/settings/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level, include_profile_extra: includeProfileExtra }),
        cache: "no-store",
      })
      const result = (await res.json()) as
        | { ok: true }
        | { ok: false; error: { message: string } }
      if (!result.ok) {
        setError(result.error.message)
        setBusy(false)
        return
      }
      window.location.reload()
    } catch {
      setError("Could not reset your preferences. Please try again.")
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" />}>
        <RotateCcw />
        Reset preferences
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reset preferences</DialogTitle>
          <DialogDescription>
            Choose a reset scope. Each reset restores exactly its namespace to the default and
            creates a restore point first, so it can be undone from Workspace management.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 flex flex-col gap-4">
          <SelectField
            id="reset-scope"
            label="Reset scope"
            value={level}
            options={RESET_OPTIONS}
            disabled={busy}
            onValueChange={(value) => value && setLevel(value)}
          />
          <p className="rounded-lg bg-muted/60 p-3 text-xs text-muted-foreground">
            {RESET_SCOPE[level] ?? RESET_SCOPE.workspace}
          </p>
          {level === "factory" && (
            <label className="flex cursor-pointer items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={includeProfileExtra}
                onChange={(event) => setIncludeProfileExtra(event.target.checked)}
              />
              <span>
                Also reset profile-extension fields
                <span className="block text-xs text-muted-foreground">
                  Clears bio, office hours, alternate email and profile picture.
                </span>
              </span>
            </label>
          )}
          {error && (
            <p className="flex items-center gap-1.5 text-sm text-destructive" role="alert">
              <TriangleAlert className="size-4 shrink-0" />
              {error}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button variant="destructive" disabled={busy} onClick={confirmReset}>
            {busy ? "Resetting…" : "Reset preferences"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
