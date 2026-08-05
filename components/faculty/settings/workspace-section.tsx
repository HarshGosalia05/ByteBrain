"use client"

import * as React from "react"
import {
  LayoutPanelLeft,
  MonitorCog,
  Rows3,
  Sidebar,
  SlidersHorizontal,
} from "lucide-react"

import type { FacultySettingsResponse } from "@/lib/faculty-api"

import { PreferenceSection } from "./preference-section"
import { SectionStatus, SelectField, SwitchRow, useSettingsSection } from "./settings-controls"
import { WorkspaceManagement } from "./workspace-management"

type WorkspacePrefs = {
  dashboard_layout: string
  compact_mode: boolean
  comfortable_mode: boolean
  table_density: string
  card_density: string
  sidebar_default_state: string
  sticky_filters: boolean
  default_page_size: string
}

type WorkspacePatch = Partial<Omit<WorkspacePrefs, "default_page_size">> & {
  default_page_size?: number
}

const DEFAULTS: WorkspacePrefs = {
  dashboard_layout: "grid",
  compact_mode: false,
  comfortable_mode: false,
  table_density: "default",
  card_density: "default",
  sidebar_default_state: "expanded",
  sticky_filters: false,
  default_page_size: "20",
}

function readWorkspace(settings: FacultySettingsResponse): WorkspacePrefs {
  const w = settings.namespaces.workspace ?? {}
  const pick = <K extends keyof WorkspacePrefs>(key: K): WorkspacePrefs[K] => {
    const value = w[key]
    if (typeof value === "boolean") return value as WorkspacePrefs[K]
    if (typeof value === "number" || typeof value === "string")
      return value as WorkspacePrefs[K]
    return DEFAULTS[key]
  }
  return {
    dashboard_layout: pick("dashboard_layout"),
    compact_mode: pick("compact_mode"),
    comfortable_mode: pick("comfortable_mode"),
    table_density: pick("table_density"),
    card_density: pick("card_density"),
    sidebar_default_state: pick("sidebar_default_state"),
    sticky_filters: pick("sticky_filters"),
    default_page_size: String(pick("default_page_size")),
  }
}

const LAYOUT_OPTIONS = [
  { value: "single", label: "Single column" },
  { value: "two_column", label: "Two columns" },
  { value: "grid", label: "Grid" },
]

const DENSITY_OPTIONS = [
  { value: "compact", label: "Compact" },
  { value: "default", label: "Default" },
  { value: "comfortable", label: "Comfortable" },
]

const SIDEBAR_OPTIONS = [
  { value: "expanded", label: "Expanded" },
  { value: "collapsed", label: "Collapsed" },
]

const PAGE_SIZE_OPTIONS = [
  { value: "10", label: "10 per page" },
  { value: "20", label: "20 per page" },
  { value: "50", label: "50 per page" },
]

export function WorkspaceSection({ settings }: { settings: FacultySettingsResponse }) {
  const [prefs, setPrefs] = React.useState<WorkspacePrefs>(() => readWorkspace(settings))
  const { saving, saved, error, apply } = useSettingsSection("workspace")

  async function patch(patch: WorkspacePatch) {
    const result = await apply(patch)
    if (result) setPrefs(readWorkspace(result))
  }

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <SectionStatus
        saving={saving}
        saved={saved}
        savedMessage="Workspace configured successfully."
        error={error}
      />

      <PreferenceSection
        icon={LayoutPanelLeft}
        title="Dashboard layout"
        description="How dashboard content is arranged on wide screens."
      >
        <div className="flex flex-col gap-5 sm:flex-row sm:flex-wrap">
          <SelectField
            id="ws-layout"
            label="Default layout"
            value={prefs.dashboard_layout}
            options={LAYOUT_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ dashboard_layout: value })}
          />
          <SelectField
            id="ws-page-size"
            label="Default page size"
            value={prefs.default_page_size}
            options={PAGE_SIZE_OPTIONS}
            disabled={saving}
            onValueChange={(value) =>
              value &&
              void patch({ default_page_size: Number.parseInt(value, 10) })
            }
          />
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={Rows3}
        title="Density"
        description="Space usage for tables, cards and dashboards."
      >
        <div className="flex flex-col gap-5 sm:flex-row sm:flex-wrap">
          <SelectField
            id="ws-table-density"
            label="Table density"
            value={prefs.table_density}
            options={DENSITY_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ table_density: value })}
          />
          <SelectField
            id="ws-card-density"
            label="Card density"
            value={prefs.card_density}
            options={DENSITY_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ card_density: value })}
          />
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={MonitorCog}
        title="General workspace"
        description="Toggles that affect density and information display across the workspace."
      >
        <SwitchRow
          id="ws-compact"
          label="Compact mode"
          description="Reduce spacing to fit more information on screen."
          checked={prefs.compact_mode}
          disabled={saving}
          onCheckedChange={(checked) => void patch({ compact_mode: checked })}
        />
        <SwitchRow
          id="ws-comfortable"
          label="Comfortable mode"
          description="Increase spacing for a more relaxed reading experience."
          checked={prefs.comfortable_mode}
          disabled={saving}
          onCheckedChange={(checked) => void patch({ comfortable_mode: checked })}
        />
      </PreferenceSection>

      <PreferenceSection
        icon={Sidebar}
        title="Sidebar"
        description="How the navigation sidebar behaves by default."
      >
        <SelectField
          id="ws-sidebar"
          label="Default state"
          value={prefs.sidebar_default_state}
          options={SIDEBAR_OPTIONS}
          disabled={saving}
            onValueChange={(value) => value && void patch({ sidebar_default_state: value })}
        />
      </PreferenceSection>

      <PreferenceSection
        icon={SlidersHorizontal}
        title="Filters"
        description="Whether filter bars stay visible while you scroll."
      >
        <SwitchRow
          id="ws-sticky"
          label="Sticky filters"
          description="Keep table and dashboard filters pinned while scrolling."
          checked={prefs.sticky_filters}
          disabled={saving}
          onCheckedChange={(checked) => void patch({ sticky_filters: checked })}
        />
      </PreferenceSection>

      <WorkspaceManagement settings={settings} />
    </div>
  )
}
