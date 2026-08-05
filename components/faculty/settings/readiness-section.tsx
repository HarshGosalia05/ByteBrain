"use client"

import { CheckCircle2, Circle, Gauge, Lightbulb } from "lucide-react"

import type { FacultyProfile, FacultySettingsResponse } from "@/lib/faculty-api"

import { PreferenceSection } from "./preference-section"

type ComponentId =
  | "profile"
  | "dashboard"
  | "notifications"
  | "accessibility"
  | "security"
  | "export"
  | "personalization"

type Component = {
  id: ComponentId
  label: string
  weight: number
  satisfied: boolean
  condition: string
  action: string
}

function nonEmpty(value: unknown): boolean {
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === "string") return value.trim().length > 0
  return Boolean(value)
}

function hasEnabledRule(rules: unknown): boolean {
  if (!Array.isArray(rules)) return false
  return rules.some((rule) => rule && typeof rule === "object" && rule.enabled === true)
}

export function computeReadiness(
  settings: FacultySettingsResponse,
  profile: FacultyProfile | null,
): { score: number; components: Component[] } {
  const namespaces = settings.namespaces
  const pick = (ns: string, key: string): unknown => {
    const record = namespaces[ns as keyof typeof namespaces]
    return typeof record === "object" && record !== null && key in record
      ? record[key as keyof typeof record]
      : undefined
  }

  const profileExtra = namespaces.profile_extra ?? {}
  const profileExtraFilled =
    nonEmpty(profileExtra.bio) ||
    nonEmpty(profileExtra.office_hours) ||
    nonEmpty(profileExtra.alternate_email) ||
    nonEmpty(profileExtra.profile_picture)
  const primaryContactPresent =
    profile != null &&
    (profile.phone_number != null ||
      (typeof profile.email === "string" && profile.email.length > 0))

  const dashboardConfigured =
    nonEmpty(pick("dashboard", "default_academic_year")) ||
    (pick("dashboard", "default_semester") ?? 0) !== 0 ||
    pick("dashboard", "default_compare") === true ||
    (pick("dashboard", "default_chart") ?? "bar") !== "bar"

  const notificationsEnabled = hasEnabledRule(pick("notifications", "rules"))

  const accessibility = namespaces.accessibility ?? {}
  const accessibilityConfigured =
    accessibility.high_contrast === true ||
    (accessibility.color_blind_palette ?? "none") !== "none" ||
    (accessibility.font_scale ?? "default") !== "default" ||
    accessibility.reduced_motion === true ||
    (accessibility.focus_ring_size ?? "default") !== "default" ||
    (accessibility.preset ?? "none") !== "none"

  const securityUpdated =
    nonEmpty(pick("security", "password_updated_at")) && settings.activity.length > 0

  const exportNs = namespaces.export ?? {}
  const exportConfigured =
    (exportNs.delimiter ?? ",") !== "," ||
    exportNs.encoding_with_bom === true ||
    (exportNs.date_format ?? "YYYY-MM-DD") !== "YYYY-MM-DD" ||
    (exportNs.time_format ?? "HH:mm") !== "HH:mm" ||
    (exportNs.decimal_precision ?? 2) !== 2 ||
    (exportNs.filename_pattern ?? "<report>_<scope>_<date>") !== "<report>_<scope>_<date>" ||
    (exportNs.timezone ?? "Asia/Kolkata") !== "Asia/Kolkata" ||
    (exportNs.default_scope ?? "current_term") !== "current_term"

  const personalization = namespaces.personalization ?? {}
  const personalized =
    nonEmpty(personalization.recent_searches) ||
    nonEmpty(personalization.favorite_filters) ||
    nonEmpty(personalization.favorite_subjects) ||
    nonEmpty(personalization.pinned_students) ||
    nonEmpty(personalization.recent_pages) ||
    nonEmpty(personalization.quick_launch_shortcuts)

  const components: Component[] = [
    {
      id: "profile",
      label: "Profile completed",
      weight: 25,
      satisfied: profileExtraFilled && primaryContactPresent,
      condition: "Bio, office hours or contact extension filled, and a phone number present.",
      action: "Add your bio and contact details to reach 25% readiness.",
    },
    {
      id: "dashboard",
      label: "Dashboard configured",
      weight: 20,
      satisfied: dashboardConfigured,
      condition: "Term scope and default chart or comparison set.",
      action: "Choose a term scope and default chart to reach 20% readiness.",
    },
    {
      id: "notifications",
      label: "Notifications enabled",
      weight: 15,
      satisfied: notificationsEnabled,
      condition: "At least one alert rule enabled.",
      action: "Enable an alert rule to reach 15% readiness.",
    },
    {
      id: "accessibility",
      label: "Accessibility configured",
      weight: 10,
      satisfied: accessibilityConfigured,
      condition: "At least one accessibility preference set beyond the default.",
      action: "Set a contrast, palette or motion preference to reach 10% readiness.",
    },
    {
      id: "security",
      label: "Security updated",
      weight: 10,
      satisfied: securityUpdated,
      condition: "Password updated and activity history present.",
      action: "Update your password through the authentication layer to reach 10% readiness.",
    },
    {
      id: "export",
      label: "Export preferences configured",
      weight: 10,
      satisfied: exportConfigured,
      condition: "At least one export preference set beyond the default.",
      action: "Customise your export format or file names to reach 10% readiness.",
    },
    {
      id: "personalization",
      label: "Workspace personalized",
      weight: 10,
      satisfied: personalized,
      condition: "Recent searches, favourites or shortcuts recorded.",
      action: "Use favourites and recent searches to reach 10% readiness.",
    },
  ]

  const score = Math.round(
    components.reduce((total, component) => total + (component.satisfied ? component.weight : 0), 0),
  )

  return { score, components }
}

export function ReadinessSection({
  settings,
  profile,
}: {
  settings: FacultySettingsResponse
  profile: FacultyProfile | null
}) {
  const { score, components } = computeReadiness(settings, profile)
  const completed = components.filter((component) => component.satisfied)
  const recommended = components.filter((component) => !component.satisfied)

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <PreferenceSection
        icon={Gauge}
        title="Workspace readiness"
        description="How completely your workspace is set up for everyday teaching. This is a descriptive measure of configuration completeness."
      >
        <div className="flex items-center gap-4">
          <div
            className="flex size-20 shrink-0 items-center justify-center rounded-full border-4 border-primary/20 bg-primary/10 text-2xl font-semibold"
            aria-label={`${score} percent ready`}
          >
            {score}%
          </div>
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">
              {completed.length === components.length
                ? "Your workspace is fully set up."
                : `${components.length - completed.length} of ${components.length} areas still need attention.`}
            </p>
            <p className="text-xs text-muted-foreground">
              {score}% = {completed.length} of {components.length} readiness areas complete.
            </p>
          </div>
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={CheckCircle2}
        title="Readiness breakdown"
        description="Weighted areas that make up your readiness score."
      >
        <div className="mt-2 flex flex-col">
          {components.map((component) => (
            <div
              key={component.id}
              className="flex items-start justify-between gap-4 border-b border-border/60 py-3 last:border-0"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  {component.satisfied ? (
                    <CheckCircle2 className="size-4 shrink-0 text-emerald-500" />
                  ) : (
                    <Circle className="size-4 shrink-0 text-muted-foreground/50" />
                  )}
                  <p className="text-sm font-medium">{component.label}</p>
                </div>
                <p className="mt-1 pl-6 text-xs text-muted-foreground">{component.condition}</p>
              </div>
              <span className="shrink-0 text-sm font-medium text-muted-foreground">
                {component.weight}%
              </span>
            </div>
          ))}
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={Lightbulb}
        title="Recommended actions"
        description="Steps that would raise your readiness score."
      >
        {recommended.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing to do — all areas are complete.</p>
        ) : (
          <ol className="mt-2 flex flex-col">
            {recommended.map((component) => (
              <li
                key={component.id}
                className="flex items-start gap-2 border-b border-border/60 py-3 last:border-0"
              >
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-muted-foreground/60" />
                <p className="text-sm">{component.action}</p>
              </li>
            ))}
          </ol>
        )}
      </PreferenceSection>
    </div>
  )
}
