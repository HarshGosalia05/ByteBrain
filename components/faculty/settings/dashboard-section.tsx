"use client"

import * as React from "react"
import { ArrowLeftRight, ChartPie, LayoutDashboard } from "lucide-react"

import type { FacultySettingsResponse } from "@/lib/faculty-api"

import { PreferenceSection } from "./preference-section"
import {
  SectionStatus,
  SelectField,
  SwitchRow,
  TextField,
  useSettingsSection,
} from "./settings-controls"

type DashboardPrefs = {
  default_semester: string
  default_academic_year: string
  default_compare: boolean
  default_chart: string
}

type DashboardPatch = Partial<Omit<DashboardPrefs, "default_semester">> & {
  default_semester?: number
}

const DEFAULTS: DashboardPrefs = {
  default_semester: "0",
  default_academic_year: "",
  default_compare: false,
  default_chart: "bar",
}

function readDashboard(settings: FacultySettingsResponse): DashboardPrefs {
  const d = settings.namespaces.dashboard ?? {}
  return {
    default_semester: String(d.default_semester ?? DEFAULTS.default_semester),
    default_academic_year:
      typeof d.default_academic_year === "string"
        ? d.default_academic_year
        : DEFAULTS.default_academic_year,
    default_compare:
      typeof d.default_compare === "boolean" ? d.default_compare : DEFAULTS.default_compare,
    default_chart:
      typeof d.default_chart === "string" ? d.default_chart : DEFAULTS.default_chart,
  }
}

const SEMESTER_OPTIONS = Array.from({ length: 9 }, (_, index) => ({
  value: String(index),
  label: index === 0 ? "Latest semester" : `Semester ${index}`,
}))

const CHART_OPTIONS = [
  { value: "bar", label: "Bar chart" },
  { value: "line", label: "Line chart" },
  { value: "donut", label: "Donut chart" },
]

export function DashboardSection({ settings }: { settings: FacultySettingsResponse }) {
  const [prefs, setPrefs] = React.useState<DashboardPrefs>(() => readDashboard(settings))
  const { saving, saved, error, apply } = useSettingsSection("dashboard")

  async function patch(patch: DashboardPatch) {
    const result = await apply(patch)
    if (result) setPrefs(readDashboard(result))
  }

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <SectionStatus
        saving={saving}
        saved={saved}
        savedMessage="Dashboard preferences updated."
        error={error}
      />

      <PreferenceSection
        icon={LayoutDashboard}
        title="Dashboard defaults"
        description="What your dashboard shows when it first loads."
      >
        <div className="flex flex-col gap-5 sm:flex-row sm:flex-wrap">
          <SelectField
            id="dash-semester"
            label="Default semester"
            description="Which semester the dashboard opens on."
            value={prefs.default_semester}
            options={SEMESTER_OPTIONS}
            disabled={saving}
            onValueChange={(value) =>
              value && void patch({ default_semester: Number.parseInt(value, 10) })
            }
          />
          <TextField
            id="dash-year"
            label="Default academic year"
            description="e.g. 2025-26. Empty uses the current year."
            value={prefs.default_academic_year}
            maxLength={20}
            disabled={saving}
            onCommit={(value) => void patch({ default_academic_year: value })}
          />
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={ChartPie}
        title="Comparison and charts"
        description="How your dashboard compares and renders analytics."
      >
        <SwitchRow
          id="dash-compare"
          label="Compare with previous term"
          description="Show the previous term comparison by default."
          checked={prefs.default_compare}
          disabled={saving}
          onCheckedChange={(checked) => void patch({ default_compare: checked })}
        />
        <div className="pt-3">
          <SelectField
            id="dash-chart"
            label="Default chart type"
            value={prefs.default_chart}
            options={CHART_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ default_chart: value })}
          />
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={ArrowLeftRight}
        title="Favourite widgets"
        description="Pinned, hidden and recent widgets are recorded as you use the dashboard."
      >
        <p className="text-sm text-muted-foreground">
          Your favourite widgets, recent items and quick-launch shortcuts are managed
          automatically as you use the portal.
        </p>
      </PreferenceSection>
    </div>
  )
}
