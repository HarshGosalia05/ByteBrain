"use client"

import * as React from "react"
import { CheckCircle2, IdCard, LoaderCircle, Mail, Pencil, TriangleAlert, UserCog, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { AvatarInitials } from "@/components/shared/data/avatar-initials"
import { ErrorState } from "@/components/shared/state/error-state"
import { ContactForm } from "@/components/faculty/profile/contact-form"
import { PreferenceSection } from "./preference-section"
import {
  type FacultyProfile,
  type FacultySettingsResponse,
} from "@/lib/faculty-api"

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

type ProfileExtra = {
  bio: string
  office_hours: string
  alternate_email: string
  profile_picture: string
}

function readExtra(settings: FacultySettingsResponse): ProfileExtra {
  const extra = settings.namespaces.profile_extra ?? {}
  return {
    bio: typeof extra.bio === "string" ? extra.bio : "",
    office_hours: typeof extra.office_hours === "string" ? extra.office_hours : "",
    alternate_email: typeof extra.alternate_email === "string" ? extra.alternate_email : "",
    profile_picture: typeof extra.profile_picture === "string" ? extra.profile_picture : "",
  }
}

function ValueRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-border/60 py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{value || "Not set"}</dd>
    </div>
  )
}

function ProfileExtraCard({ settings }: { settings: FacultySettingsResponse }) {
  const initial = readExtra(settings)
  const [editing, setEditing] = React.useState(false)
  const [bio, setBio] = React.useState(initial.bio)
  const [officeHours, setOfficeHours] = React.useState(initial.office_hours)
  const [alternateEmail, setAlternateEmail] = React.useState(initial.alternate_email)
  const [profilePicture, setProfilePicture] = React.useState(initial.profile_picture)
  const [saving, setSaving] = React.useState(false)
  const [saved, setSaved] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  async function handleSave() {
    const next = {
      bio: bio.trim(),
      office_hours: officeHours.trim(),
      alternate_email: alternateEmail.trim(),
      profile_picture: profilePicture.trim(),
    }

    if (next.alternate_email && !EMAIL_PATTERN.test(next.alternate_email)) {
      setError("Enter a valid alternate email address.")
      return
    }

    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const res = await fetch("/api/faculty/settings/profile_extra", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
        cache: "no-store",
      })
      const result = (await res.json()) as
        | { ok: true; data: FacultySettingsResponse }
        | { ok: false; error: { message: string } }
      if (!result.ok) {
        setError(result.error.message)
        return
      }
      setSaved(true)
      setEditing(false)
    } catch {
      setError("Could not update your extended profile. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  function handleCancel() {
    setEditing(false)
    setError(null)
    setSaved(false)
    setBio(initial.bio)
    setOfficeHours(initial.office_hours)
    setAlternateEmail(initial.alternate_email)
    setProfilePicture(initial.profile_picture)
  }

  return (
    <PreferenceSection
      icon={UserCog}
      title="Extended profile"
      description="Optional details that personalise how you appear across the portal."
      action={
        !editing && (
          <Button variant="ghost" size="sm" onClick={() => setEditing(true)} className="gap-2">
            <Pencil className="size-3.5" />
            Edit
          </Button>
        )
      }
    >
      {editing ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="profile-bio">Bio</Label>
            <Textarea
              id="profile-bio"
              value={bio}
              onChange={(event) => setBio(event.target.value)}
              maxLength={500}
              rows={3}
              placeholder="A short introduction shown to colleagues."
            />
            <p className="text-xs text-muted-foreground">{bio.length} / 500</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="profile-office-hours">Office hours</Label>
              <Input
                id="profile-office-hours"
                value={officeHours}
                onChange={(event) => setOfficeHours(event.target.value)}
                maxLength={200}
                placeholder="e.g. Mon–Fri, 10:00–12:00"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="profile-alternate-email">Alternate email</Label>
              <Input
                id="profile-alternate-email"
                type="email"
                value={alternateEmail}
                onChange={(event) => setAlternateEmail(event.target.value)}
                placeholder="you@example.com"
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="profile-picture">Profile picture URL</Label>
            <Input
              id="profile-picture"
              type="url"
              value={profilePicture}
              onChange={(event) => setProfilePicture(event.target.value)}
              maxLength={1000}
              placeholder="https://example.com/avatar.png"
            />
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
            <Button size="sm" variant="ghost" onClick={handleCancel} disabled={saving} className="gap-2">
              <X className="size-3.5" />
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <dl>
          <ValueRow label="Bio" value={initial.bio} />
          <ValueRow label="Office hours" value={initial.office_hours} />
          <ValueRow label="Alternate email" value={initial.alternate_email} />
          <ValueRow label="Profile picture" value={initial.profile_picture} />
        </dl>
      )}

      {saved && !editing && (
        <p className="mt-3 flex items-center gap-1.5 text-sm text-chart-2" role="status">
          <CheckCircle2 className="size-4 shrink-0" />
          Your extended profile was updated.
        </p>
      )}
    </PreferenceSection>
  )
}

export function ProfileSection({
  profile,
  settings,
}: {
  profile: FacultyProfile | null
  settings: FacultySettingsResponse
}) {
  if (!profile) {
    return (
      <ErrorState
        title="Profile unavailable"
        description="We could not load your profile details. Please try again later."
      />
    )
  }

  const firstName = profile.full_name.split(" ")[0] ?? ""
  const lastName = profile.full_name.split(" ").slice(1).join(" ") ?? ""

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <PreferenceSection
        icon={IdCard}
        title="Identity"
        description="Your official record. Identity fields are managed by the administration."
      >
        <div className="flex flex-wrap items-center gap-4">
          <AvatarInitials firstName={firstName} lastName={lastName} size="lg" />
          <div className="min-w-0 flex-1">
            <p className="text-base font-semibold tracking-tight">{profile.full_name}</p>
            <p className="text-sm text-muted-foreground">{profile.faculty_id}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {profile.designation && <Badge variant="default">{profile.designation}</Badge>}
              {profile.department_name && <Badge variant="outline">{profile.department_name}</Badge>}
              {profile.joining_date && <Badge variant="muted">Joined {profile.joining_date}</Badge>}
            </div>
          </div>
        </div>
        <dl className="mt-4">
          <ValueRow label="Faculty code" value={profile.faculty_code} />
          <ValueRow label="Qualification" value={profile.qualification ?? ""} />
          <ValueRow label="Specialization" value={profile.specialization ?? ""} />
          <ValueRow
            label="Experience"
            value={profile.experience_years ? `${profile.experience_years} years` : ""}
          />
          <ValueRow label="Employment type" value={profile.employment_type ?? ""} />
          <ValueRow label="Status" value={profile.status ?? ""} />
        </dl>
      </PreferenceSection>

      <PreferenceSection
        icon={Mail}
        title="Contact information"
        description="Email and phone are the only contact fields you can edit yourself."
      >
        <ContactForm profile={profile} />
      </PreferenceSection>

      <ProfileExtraCard settings={settings} />
    </div>
  )
}
