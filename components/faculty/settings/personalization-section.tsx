"use client"

import { Sparkles } from "lucide-react"

import type { FacultySettingsResponse } from "@/lib/faculty-api"

import { PreferenceSection } from "./preference-section"

export function PersonalizationSection({ settings }: { settings: FacultySettingsResponse }) {
  const personalization = settings.namespaces.personalization ?? {}
  const items: { key: string; label: string; value: unknown }[] = [
    { key: "recent_searches", label: "Recent searches", value: personalization.recent_searches },
    { key: "favorite_filters", label: "Favourite filters", value: personalization.favorite_filters },
    { key: "favorite_subjects", label: "Favourite subjects", value: personalization.favorite_subjects },
    { key: "pinned_students", label: "Pinned students", value: personalization.pinned_students },
    { key: "recent_pages", label: "Recent pages", value: personalization.recent_pages },
    {
      key: "quick_launch_shortcuts",
      label: "Quick-launch shortcuts",
      value: personalization.quick_launch_shortcuts,
    },
  ]

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <PreferenceSection
        icon={Sparkles}
        title="Personalisation"
        description="Items the system remembers for you are tracked automatically as you use the portal."
      >
        <p className="text-sm text-muted-foreground">
          These are managed by the system based on your activity. You can clear them at any
          time from the workspace management section.
        </p>
        <dl className="mt-4">
          {items.map((item) => {
            const count = Array.isArray(item.value) ? item.value.length : 0
            return (
              <div
                key={item.key}
                className="flex items-center justify-between border-b border-border/60 py-3 last:border-0"
              >
                <dt className="text-sm text-muted-foreground">{item.label}</dt>
                <dd className="text-sm font-medium">
                  {count === 0 ? "None" : `${count} item${count === 1 ? "" : "s"}`}
                </dd>
              </div>
            )
          })}
        </dl>
      </PreferenceSection>
    </div>
  )
}
