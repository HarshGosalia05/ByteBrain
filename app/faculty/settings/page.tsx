import { requireRole } from "@/lib/session"
import { getFacultyProfile, getFacultySettings } from "@/lib/faculty-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { ErrorState } from "@/components/shared/state/error-state"
import { SettingsView } from "@/components/faculty/settings/settings-view"
import {
  DEFAULT_SETTINGS_TAB,
  SETTINGS_TABS,
} from "@/components/faculty/settings/settings-tabs"

export default async function SettingsPage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Faculty")

  const searchParams = await props.searchParams
  const requestedTab = typeof searchParams.tab === "string" ? searchParams.tab : ""
  const tab = SETTINGS_TABS.some((entry) => entry.id === requestedTab)
    ? requestedTab
    : DEFAULT_SETTINGS_TAB

  const [settingsResult, profileResult] = await Promise.all([
    getFacultySettings(),
    getFacultyProfile(),
  ])
  if (!settingsResult.ok) {
    return <ErrorState title="Settings unavailable" description={settingsResult.error.message} />
  }

  const fetchedAt =
    settingsResult.data.metadata.last_modified ??
    [settingsResult, profileResult]
      .filter((r) => r.ok)
      .map((r) => r.fetchedAt)
      .sort()
      .pop()

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Settings"
        description="Personalise your faculty workspace, analytics, notifications and preferences."
        fetchedAt={fetchedAt}
      />
      <SettingsView
        activeTab={tab}
        settings={settingsResult.data}
        profile={profileResult.ok ? profileResult.data : null}
      />
    </div>
  )
}
