"use client"

import * as React from "react"
import { Bell, BellRing, Moon, Plus, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import type { FacultySettingsResponse } from "@/lib/faculty-api"

import { PreferenceSection } from "./preference-section"
import {
  SectionStatus,
  SelectField,
  SwitchRow,
  TextField,
  useSettingsSection,
} from "./settings-controls"

type NotificationRule = {
  id: string
  alert_type: string
  threshold: number
  enabled: boolean
}

type NotificationsPrefs = {
  rules: NotificationRule[]
  quiet_hours_enabled: boolean
  quiet_hours_start: string
  quiet_hours_end: string
  dnd_enabled: boolean
  dnd_until: string
  digest_frequency: string
  browser_enabled: boolean
}

const DEFAULTS: NotificationsPrefs = {
  rules: [],
  quiet_hours_enabled: false,
  quiet_hours_start: "22:00",
  quiet_hours_end: "07:00",
  dnd_enabled: false,
  dnd_until: "",
  digest_frequency: "immediate",
  browser_enabled: true,
}

function readRule(value: unknown): NotificationRule | null {
  if (!value || typeof value !== "object") return null
  const rule = value as Record<string, unknown>
  if (typeof rule.id !== "string" || typeof rule.alert_type !== "string") return null
  return {
    id: rule.id,
    alert_type: rule.alert_type,
    threshold: typeof rule.threshold === "number" ? rule.threshold : 0,
    enabled: typeof rule.enabled === "boolean" ? rule.enabled : true,
  }
}

function readNotifications(settings: FacultySettingsResponse): NotificationsPrefs {
  const n = settings.namespaces.notifications ?? {}
  const quiet = (n.quiet_hours ?? {}) as Record<string, unknown>
  const dnd = (n.do_not_disturb ?? {}) as Record<string, unknown>
  return {
    rules: Array.isArray(n.rules)
      ? n.rules.map(readRule).filter((rule): rule is NotificationRule => rule !== null)
      : DEFAULTS.rules,
    quiet_hours_enabled:
      typeof quiet.enabled === "boolean" ? quiet.enabled : DEFAULTS.quiet_hours_enabled,
    quiet_hours_start:
      typeof quiet.start === "string" ? quiet.start : DEFAULTS.quiet_hours_start,
    quiet_hours_end: typeof quiet.end === "string" ? quiet.end : DEFAULTS.quiet_hours_end,
    dnd_enabled: typeof dnd.enabled === "boolean" ? dnd.enabled : DEFAULTS.dnd_enabled,
    dnd_until: typeof dnd.until === "string" ? dnd.until : DEFAULTS.dnd_until,
    digest_frequency:
      typeof n.digest_frequency === "string"
        ? n.digest_frequency
        : DEFAULTS.digest_frequency,
    browser_enabled:
      typeof n.browser_enabled === "boolean" ? n.browser_enabled : DEFAULTS.browser_enabled,
  }
}

const ALERT_TYPE_OPTIONS = [
  { value: "attendance", label: "Attendance" },
  { value: "performance", label: "Performance" },
  { value: "workload", label: "Workload" },
]

const ALERT_TYPE_LABELS: Record<string, string> = {
  attendance: "Attendance",
  performance: "Performance",
  workload: "Workload",
}

const DIGEST_OPTIONS = [
  { value: "immediate", label: "Immediately" },
  { value: "daily", label: "Daily digest" },
  { value: "weekly", label: "Weekly digest" },
]

export function NotificationsSection({ settings }: { settings: FacultySettingsResponse }) {
  const [prefs, setPrefs] = React.useState<NotificationsPrefs>(() =>
    readNotifications(settings),
  )
  const { saving, saved, error, apply } = useSettingsSection("notifications")

  const [newType, setNewType] = React.useState("attendance")
  const [newThreshold, setNewThreshold] = React.useState("75")

  async function patch(patch: Record<string, unknown>) {
    const result = await apply(patch)
    if (result) setPrefs(readNotifications(result))
  }

  function patchQuietHours(next: Partial<{ enabled: boolean; start: string; end: string }>) {
    void patch({
      quiet_hours: {
        enabled: prefs.quiet_hours_enabled,
        start: prefs.quiet_hours_start,
        end: prefs.quiet_hours_end,
        ...next,
      },
    })
  }

  function patchDnd(next: Partial<{ enabled: boolean; until: string }>) {
    void patch({
      do_not_disturb: { enabled: prefs.dnd_enabled, until: prefs.dnd_until, ...next },
    })
  }

  function addRule() {
    const threshold = Number(newThreshold)
    if (!Number.isFinite(threshold)) return
    const rule: NotificationRule = {
      id: typeof crypto !== "undefined" ? crypto.randomUUID() : String(Date.now()),
      alert_type: newType,
      threshold,
      enabled: true,
    }
    void patch({ rules: [...prefs.rules, rule] })
  }

  function updateRule(id: string, next: Partial<NotificationRule>) {
    void patch({
      rules: prefs.rules.map((rule) => (rule.id === id ? { ...rule, ...next } : rule)),
    })
  }

  function deleteRule(id: string) {
    void patch({ rules: prefs.rules.filter((rule) => rule.id !== id) })
  }

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <SectionStatus
        saving={saving}
        saved={saved}
        savedMessage="Notification preferences updated."
        error={error}
      />

      <PreferenceSection
        icon={BellRing}
        title="Alert rules"
        description="Rule-based alerts are generated from the same deterministic analytics your pages compute."
      >
        <div className="flex flex-col gap-3">
          {prefs.rules.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No alert rules yet. Add a rule to flag students against a threshold.
            </p>
          ) : (
            prefs.rules.map((rule) => (
              <div
                key={rule.id}
                className="flex items-center justify-between gap-4 rounded-lg border border-border/60 px-3 py-2.5"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Bell className="size-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      {ALERT_TYPE_LABELS[rule.alert_type] ?? rule.alert_type}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Threshold: {rule.threshold}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={rule.enabled}
                    onCheckedChange={(checked) => void updateRule(rule.id, { enabled: checked })}
                    disabled={saving}
                    aria-label={`Enable ${rule.alert_type} rule`}
                  />
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => deleteRule(rule.id)}
                    disabled={saving}
                    aria-label={`Delete ${rule.alert_type} rule`}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            ))
          )}

          <div className="flex flex-col gap-3 rounded-lg border border-dashed border-border bg-muted/30 p-3 sm:flex-row sm:items-end">
            <SelectField
              id="nt-new-type"
              label="Alert type"
              value={newType}
              options={ALERT_TYPE_OPTIONS}
              disabled={saving}
              onValueChange={(value) => value && setNewType(value)}
            />
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium leading-none">Threshold</span>
              <Input
                aria-label="Rule threshold"
                inputMode="decimal"
                value={newThreshold}
                disabled={saving}
                onChange={(event) => setNewThreshold(event.target.value)}
                className="w-full sm:w-40"
              />
            </div>
            <Button size="sm" onClick={addRule} disabled={saving} className="gap-1.5">
              <Plus className="size-4" />
              Add rule
            </Button>
          </div>
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={Moon}
        title="Quiet hours"
        description="Suppress non-critical alerts during a daily time window."
      >
        <SwitchRow
          id="nt-quiet-enabled"
          label="Enable quiet hours"
          description="Alerts below priority are held during this window."
          checked={prefs.quiet_hours_enabled}
          disabled={saving}
          onCheckedChange={(checked) => void patchQuietHours({ enabled: checked })}
        />
        <div className="flex flex-col gap-5 pt-3 sm:flex-row sm:flex-wrap">
          <TextField
            id="nt-quiet-start"
            label="Start"
            type="time"
            value={prefs.quiet_hours_start}
            disabled={saving || !prefs.quiet_hours_enabled}
            onCommit={(value) => void patchQuietHours({ start: value })}
          />
          <TextField
            id="nt-quiet-end"
            label="End"
            type="time"
            value={prefs.quiet_hours_end}
            disabled={saving || !prefs.quiet_hours_enabled}
            onCommit={(value) => void patchQuietHours({ end: value })}
          />
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={Bell}
        title="Do Not Disturb"
        description="Suppress all alerts until you turn it off or the timer expires."
      >
        <SwitchRow
          id="nt-dnd-enabled"
          label="Enable Do Not Disturb"
          description="No alerts are delivered while active."
          checked={prefs.dnd_enabled}
          disabled={saving}
          onCheckedChange={(checked) => void patchDnd({ enabled: checked })}
        />
        <div className="pt-3">
          <TextField
            id="nt-dnd-until"
            label="Until"
            type="time"
            value={prefs.dnd_until}
            disabled={saving || !prefs.dnd_enabled}
            onCommit={(value) => void patchDnd({ until: value })}
          />
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={BellRing}
        title="Digest and channel"
        description="How and where alerts reach you."
      >
        <SelectField
          id="nt-digest"
          label="Digest frequency"
          value={prefs.digest_frequency}
          options={DIGEST_OPTIONS}
          disabled={saving}
          onValueChange={(value) => value && void patch({ digest_frequency: value })}
        />
        <div className="mt-2">
          <SwitchRow
            id="nt-browser"
            label="Browser notifications"
            description="Deliver alerts through the browser. Browser is the only channel in this version."
            checked={prefs.browser_enabled}
            disabled={saving}
            onCheckedChange={(checked) => void patch({ browser_enabled: checked })}
          />
        </div>
      </PreferenceSection>
    </div>
  )
}
