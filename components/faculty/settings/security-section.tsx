"use client"

import { History, KeyRound, MonitorSmartphone } from "lucide-react"

import { EmptyState } from "@/components/shared/state/empty-state"
import type { FacultySettingsResponse } from "@/lib/faculty-api"

import { PreferenceSection } from "./preference-section"

function ValueRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-border/60 py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="break-all text-sm font-medium">{value || "Not available"}</dd>
    </div>
  )
}

function CurrentSessionCard({ session }: { session: Record<string, unknown> }) {
  const pick = (key: string): string =>
    typeof session[key] === "string" ? (session[key] as string) : ""
  return (
    <PreferenceSection
      icon={MonitorSmartphone}
      title="Current session"
      description="The session you are currently signed in with."
    >
      <dl>
        <ValueRow label="Session ID" value={pick("id")} />
        <ValueRow label="Started" value={pick("started_at")} />
        <ValueRow label="IP address" value={pick("ip")} />
        <ValueRow label="Browser" value={pick("user_agent")} />
      </dl>
    </PreferenceSection>
  )
}

export function SecuritySection({ settings }: { settings: FacultySettingsResponse }) {
  const security = settings.namespaces.security ?? {}
  const session = (security.current_session ?? {}) as Record<string, unknown>
  const passwordUpdatedAt =
    typeof security.password_updated_at === "string" ? security.password_updated_at : ""
  const lastLogin = typeof security.last_login === "string" ? security.last_login : ""
  const activity = settings.activity ?? []

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <PreferenceSection
        icon={KeyRound}
        title="Password"
        description="Password changes are handled through the authentication layer."
      >
        <dl>
          <ValueRow label="Last changed" value={passwordUpdatedAt} />
          <ValueRow label="Last sign-in" value={lastLogin} />
        </dl>
        <p className="mt-3 text-xs text-muted-foreground">
          Two-factor authentication and passkeys are planned for a future version.
        </p>
      </PreferenceSection>

      <CurrentSessionCard session={session} />

      <PreferenceSection
        icon={History}
        title="Recent activity"
        description="Recent preference changes made to your workspace."
      >
        {activity.length === 0 ? (
          <EmptyState
            title="No activity yet"
            description="Changes you make to your preferences will appear here."
          />
        ) : (
          <ol className="flex flex-col">
            {activity.map((entry, index) => (
              <li
                key={`${entry.at}-${index}`}
                className="flex items-start justify-between gap-4 border-b border-border/60 py-3 last:border-0"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">
                    {entry.event === "preference_change" ? "Preference change" : entry.event}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {entry.namespace && (
                      <span className="font-medium">{entry.namespace}</span>
                    )}
                    {entry.detail ? ` — ${entry.detail}` : ""}
                  </p>
                </div>
                <time className="shrink-0 text-xs text-muted-foreground">{entry.at}</time>
              </li>
            ))}
          </ol>
        )}
      </PreferenceSection>
    </div>
  )
}
