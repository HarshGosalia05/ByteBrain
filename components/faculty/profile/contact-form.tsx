"use client"

import * as React from "react"
import { CheckCircle2, LoaderCircle, Pencil, TriangleAlert, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { FacultyProfile } from "@/lib/faculty-api"

export function ContactForm({ profile }: { profile: FacultyProfile }) {
  const [editing, setEditing] = React.useState(false)
  const [email, setEmail] = React.useState(profile.email ?? "")
  const [phone, setPhone] = React.useState(profile.phone_number?.toString() ?? "")
  const [saving, setSaving] = React.useState(false)
  const [saved, setSaved] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  async function handleSave() {
    const trimmedEmail = email.trim()
    const trimmedPhone = phone.trim()

    if (!trimmedEmail) {
      setError("Email is required.")
      return
    }
    if (!trimmedPhone || Number.isNaN(Number(trimmedPhone))) {
      setError("A valid phone number is required.")
      return
    }

    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const res = await fetch("/api/faculty/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: trimmedEmail,
          phone_number: Number(trimmedPhone),
        }),
      })
      const result = await res.json()
      if (!result.ok) {
        setError(result.error?.message ?? "Could not update your contact details.")
        return
      }
      setSaved(true)
      setEditing(false)
    } catch {
      setError("Could not update your contact details. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">Contact information</p>
          <p className="text-xs text-muted-foreground">
            Email and phone are the only fields you can edit yourself.
          </p>
        </div>
        {!editing && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setEditing(true)}
            className="gap-2"
          >
            <Pencil className="size-3.5" />
            Edit
          </Button>
        )}
      </div>

      {editing ? (
        <div className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="faculty-email">Email</Label>
              <Input
                id="faculty-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="faculty-phone">Phone number</Label>
              <Input
                id="faculty-phone"
                type="tel"
                inputMode="numeric"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
            </div>
          </div>
          {error && (
            <p className="flex items-center gap-1.5 text-sm text-destructive" role="alert">
              <TriangleAlert className="size-4 shrink-0" />
              {error}
            </p>
          )}
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={handleSave} disabled={saving} className="gap-2">
              {saving && <LoaderCircle className="size-3.5 animate-spin" />}
              Save
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setEditing(false)
                setError(null)
                setSaved(false)
                setEmail(profile.email ?? "")
                setPhone(profile.phone_number?.toString() ?? "")
              }}
              disabled={saving}
              className="gap-2"
            >
              <X className="size-3.5" />
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <dl>
          <div className="flex flex-col gap-0.5 border-b border-border/60 py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
            <dt className="text-sm text-muted-foreground">Email</dt>
            <dd className="text-sm font-medium tabular-nums">{profile.email ?? "—"}</dd>
          </div>
          <div className="flex flex-col gap-0.5 border-b border-border/60 py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
            <dt className="text-sm text-muted-foreground">Phone number</dt>
            <dd className="text-sm font-medium tabular-nums">
              {profile.phone_number?.toString() ?? "—"}
            </dd>
          </div>
        </dl>
      )}

      {saved && !editing && (
        <p className="flex items-center gap-1.5 text-sm text-chart-2" role="status">
          <CheckCircle2 className="size-4 shrink-0" />
          Your contact details were updated.
        </p>
      )}
    </div>
  )
}
