import type { FacultyProfile, FacultySettingsResponse } from "@/lib/faculty-api"

import { AccessibilitySection } from "./accessibility-section"
import { AnalyticsSection } from "./analytics-section"
import { DashboardSection } from "./dashboard-section"
import { ExportSection } from "./export-section"
import { NotificationsSection } from "./notifications-section"
import { PersonalizationSection } from "./personalization-section"
import { ProfileSection } from "./profile-section"
import { ReadinessSection } from "./readiness-section"
import { SecuritySection } from "./security-section"
import { WorkspaceSection } from "./workspace-section"
import { SectionPlaceholder } from "./section-placeholder"
import { SETTINGS_TABS } from "./settings-tabs"

export function SettingsSection({
  activeTab,
  settings,
  profile,
}: {
  activeTab: string
  settings: FacultySettingsResponse
  profile: FacultyProfile | null
}) {
  if (activeTab === "profile") {
    return <ProfileSection profile={profile} settings={settings} />
  }

  if (activeTab === "workspace") {
    return <WorkspaceSection settings={settings} />
  }

  if (activeTab === "dashboard") {
    return <DashboardSection settings={settings} />
  }

  if (activeTab === "analytics") {
    return <AnalyticsSection settings={settings} />
  }

  if (activeTab === "notifications") {
    return <NotificationsSection settings={settings} />
  }

  if (activeTab === "export") {
    return <ExportSection settings={settings} />
  }

  if (activeTab === "accessibility") {
    return <AccessibilitySection settings={settings} />
  }

  if (activeTab === "personalization") {
    return <PersonalizationSection settings={settings} />
  }

  if (activeTab === "security") {
    return <SecuritySection settings={settings} />
  }

  if (activeTab === "readiness") {
    return <ReadinessSection settings={settings} profile={profile} />
  }

  const tab = SETTINGS_TABS.find((entry) => entry.id === activeTab) ?? SETTINGS_TABS[0]
  return <SectionPlaceholder icon={tab.icon} title={tab.label} description={tab.description} />
}
