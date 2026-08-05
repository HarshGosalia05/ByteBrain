"use client"

import * as React from "react"
import { ChartColumn, Gauge, Table2 } from "lucide-react"

import type { FacultySettingsResponse } from "@/lib/faculty-api"

import { PreferenceSection } from "./preference-section"
import {
  NumberField,
  SectionStatus,
  SelectField,
  SwitchRow,
  useSettingsSection,
} from "./settings-controls"

type AnalyticsPrefs = {
  attendance_threshold_override: number | null
  performance_threshold_override: number | null
  workload_capacity_hours_override: number | null
  overload_threshold_override: number | null
  underutilized_threshold_override: number | null
  default_compare_mode: string
  chart_tooltips: boolean
  chart_legend_position: string
  auto_refresh: boolean
  sorting_field: string
  sorting_order: string
  table_page_size: string
  table_density: string
}

type AnalyticsPatch = Partial<Omit<AnalyticsPrefs, "table_page_size">> & {
  table_page_size?: number
}

const DEFAULTS: AnalyticsPrefs = {
  attendance_threshold_override: null,
  performance_threshold_override: null,
  workload_capacity_hours_override: null,
  overload_threshold_override: null,
  underutilized_threshold_override: null,
  default_compare_mode: "auto",
  chart_tooltips: true,
  chart_legend_position: "bottom",
  auto_refresh: false,
  sorting_field: "attendance",
  sorting_order: "desc",
  table_page_size: "20",
  table_density: "default",
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function readAnalytics(settings: FacultySettingsResponse): AnalyticsPrefs {
  const a = settings.namespaces.analytics ?? {}
  return {
    attendance_threshold_override: readNumber(a.attendance_threshold_override),
    performance_threshold_override: readNumber(a.performance_threshold_override),
    workload_capacity_hours_override: readNumber(a.workload_capacity_hours_override),
    overload_threshold_override: readNumber(a.overload_threshold_override),
    underutilized_threshold_override: readNumber(a.underutilized_threshold_override),
    default_compare_mode:
      typeof a.default_compare_mode === "string"
        ? a.default_compare_mode
        : DEFAULTS.default_compare_mode,
    chart_tooltips:
      typeof a.chart_tooltips === "boolean" ? a.chart_tooltips : DEFAULTS.chart_tooltips,
    chart_legend_position:
      typeof a.chart_legend_position === "string"
        ? a.chart_legend_position
        : DEFAULTS.chart_legend_position,
    auto_refresh:
      typeof a.auto_refresh === "boolean" ? a.auto_refresh : DEFAULTS.auto_refresh,
    sorting_field:
      typeof a.sorting_field === "string" ? a.sorting_field : DEFAULTS.sorting_field,
    sorting_order:
      typeof a.sorting_order === "string" ? a.sorting_order : DEFAULTS.sorting_order,
    table_page_size: String(a.table_page_size ?? DEFAULTS.table_page_size),
    table_density:
      typeof a.table_density === "string" ? a.table_density : DEFAULTS.table_density,
  }
}

const COMPARE_MODE_OPTIONS = [
  { value: "auto", label: "Automatic" },
  { value: "on", label: "Always on" },
  { value: "off", label: "Always off" },
]

const LEGEND_OPTIONS = [
  { value: "bottom", label: "Bottom" },
  { value: "right", label: "Right" },
  { value: "top", label: "Top" },
  { value: "hidden", label: "Hidden" },
]

const SORTING_FIELD_OPTIONS = [
  { value: "attendance", label: "Attendance" },
  { value: "performance", label: "Performance" },
  { value: "pass_rate", label: "Pass rate" },
  { value: "credits", label: "Credits" },
  { value: "students", label: "Students" },
]

const SORTING_ORDER_OPTIONS = [
  { value: "desc", label: "Descending" },
  { value: "asc", label: "Ascending" },
]

const PAGE_SIZE_OPTIONS = [
  { value: "10", label: "10 per page" },
  { value: "20", label: "20 per page" },
  { value: "50", label: "50 per page" },
]

const DENSITY_OPTIONS = [
  { value: "compact", label: "Compact" },
  { value: "default", label: "Default" },
  { value: "comfortable", label: "Comfortable" },
]

export function AnalyticsSection({ settings }: { settings: FacultySettingsResponse }) {
  const [prefs, setPrefs] = React.useState<AnalyticsPrefs>(() => readAnalytics(settings))
  const { saving, saved, error, apply } = useSettingsSection("analytics")

  async function patch(patch: AnalyticsPatch) {
    const result = await apply(patch)
    if (result) setPrefs(readAnalytics(result))
  }

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <SectionStatus
        saving={saving}
        saved={saved}
        savedMessage="Analytics preferences updated."
        error={error}
      />

      <PreferenceSection
        icon={Gauge}
        title="Threshold overrides"
        description="Override the analytical baselines used to flag students. Values are validated against admin-defined bounds."
      >
        <div className="grid gap-5 sm:grid-cols-2">
          <NumberField
            id="an-attendance"
            label="Attendance threshold (%)"
            value={prefs.attendance_threshold_override}
            min={50}
            max={95}
            disabled={saving}
            onCommit={(value) => void patch({ attendance_threshold_override: value })}
          />
          <NumberField
            id="an-performance"
            label="Performance threshold (%)"
            value={prefs.performance_threshold_override}
            min={40}
            max={90}
            disabled={saving}
            onCommit={(value) => void patch({ performance_threshold_override: value })}
          />
          <NumberField
            id="an-capacity"
            label="Workload capacity (hours/week)"
            value={prefs.workload_capacity_hours_override}
            min={12}
            max={40}
            disabled={saving}
            onCommit={(value) => void patch({ workload_capacity_hours_override: value })}
          />
          <NumberField
            id="an-overload"
            label="Overload ratio"
            value={prefs.overload_threshold_override}
            min={0.8}
            max={0.95}
            disabled={saving}
            onCommit={(value) => void patch({ overload_threshold_override: value })}
          />
          <NumberField
            id="an-underutilized"
            label="Underutilized ratio"
            value={prefs.underutilized_threshold_override}
            min={0.25}
            max={0.5}
            disabled={saving}
            onCommit={(value) => void patch({ underutilized_threshold_override: value })}
          />
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={ChartColumn}
        title="Charts and comparison"
        description="How analytics charts render and compare data."
      >
        <div className="flex flex-col gap-5 sm:flex-row sm:flex-wrap">
          <SelectField
            id="an-compare"
            label="Comparison mode"
            value={prefs.default_compare_mode}
            options={COMPARE_MODE_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ default_compare_mode: value })}
          />
          <SelectField
            id="an-legend"
            label="Legend position"
            value={prefs.chart_legend_position}
            options={LEGEND_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ chart_legend_position: value })}
          />
        </div>
        <div className="mt-2">
          <SwitchRow
            id="an-tooltips"
            label="Chart tooltips"
            description="Show values when hovering over chart points."
            checked={prefs.chart_tooltips}
            disabled={saving}
            onCheckedChange={(checked) => void patch({ chart_tooltips: checked })}
          />
          <SwitchRow
            id="an-refresh"
            label="Auto-refresh"
            description="Automatically refresh analytics data while viewing."
            checked={prefs.auto_refresh}
            disabled={saving}
            onCheckedChange={(checked) => void patch({ auto_refresh: checked })}
          />
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={Table2}
        title="Tables"
        description="Sorting and layout of analytics tables."
      >
        <div className="flex flex-col gap-5 sm:flex-row sm:flex-wrap">
          <SelectField
            id="an-sort-field"
            label="Default sort"
            value={prefs.sorting_field}
            options={SORTING_FIELD_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ sorting_field: value })}
          />
          <SelectField
            id="an-sort-order"
            label="Sort order"
            value={prefs.sorting_order}
            options={SORTING_ORDER_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ sorting_order: value })}
          />
          <SelectField
            id="an-page-size"
            label="Rows per page"
            value={prefs.table_page_size}
            options={PAGE_SIZE_OPTIONS}
            disabled={saving}
            onValueChange={(value) =>
              value && void patch({ table_page_size: Number.parseInt(value, 10) })
            }
          />
          <SelectField
            id="an-density"
            label="Table density"
            value={prefs.table_density}
            options={DENSITY_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ table_density: value })}
          />
        </div>
      </PreferenceSection>
    </div>
  )
}
