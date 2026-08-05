"use client"

import * as React from "react"
import { FileDown, FileType, Tags } from "lucide-react"

import type { FacultySettingsResponse } from "@/lib/faculty-api"

import { PreferenceSection } from "./preference-section"
import {
  SectionStatus,
  SelectField,
  SwitchRow,
  TextField,
  useSettingsSection,
} from "./settings-controls"

type ExportPrefs = {
  delimiter: string
  encoding_with_bom: boolean
  date_format: string
  time_format: string
  decimal_precision: string
  filename_pattern: string
  timezone: string
  default_scope: string
}

type ExportPatch = Partial<Omit<ExportPrefs, "decimal_precision">> & {
  decimal_precision?: number
}

const DEFAULTS: ExportPrefs = {
  delimiter: ",",
  encoding_with_bom: false,
  date_format: "YYYY-MM-DD",
  time_format: "HH:mm",
  decimal_precision: "2",
  filename_pattern: "<report>_<scope>_<date>",
  timezone: "Asia/Kolkata",
  default_scope: "current_term",
}

function readExport(settings: FacultySettingsResponse): ExportPrefs {
  const e = settings.namespaces.export ?? {}
  return {
    delimiter: typeof e.delimiter === "string" ? e.delimiter : DEFAULTS.delimiter,
    encoding_with_bom:
      typeof e.encoding_with_bom === "boolean"
        ? e.encoding_with_bom
        : DEFAULTS.encoding_with_bom,
    date_format: typeof e.date_format === "string" ? e.date_format : DEFAULTS.date_format,
    time_format: typeof e.time_format === "string" ? e.time_format : DEFAULTS.time_format,
    decimal_precision: String(e.decimal_precision ?? DEFAULTS.decimal_precision),
    filename_pattern:
      typeof e.filename_pattern === "string" ? e.filename_pattern : DEFAULTS.filename_pattern,
    timezone: typeof e.timezone === "string" ? e.timezone : DEFAULTS.timezone,
    default_scope:
      typeof e.default_scope === "string" ? e.default_scope : DEFAULTS.default_scope,
  }
}

const DELIMITER_OPTIONS = [
  { value: ",", label: "Comma (,)" },
  { value: ";", label: "Semicolon (;)" },
  { value: "|", label: "Pipe (|)" },
  { value: "\t", label: "Tab" },
]

const DATE_FORMAT_OPTIONS = [
  { value: "YYYY-MM-DD", label: "YYYY-MM-DD" },
  { value: "DD-MM-YYYY", label: "DD-MM-YYYY" },
  { value: "MM/DD/YYYY", label: "MM/DD/YYYY" },
]

const TIME_FORMAT_OPTIONS = [
  { value: "HH:mm", label: "24-hour (HH:mm)" },
  { value: "hh:mm A", label: "12-hour (hh:mm AM/PM)" },
]

const PRECISION_OPTIONS = Array.from({ length: 7 }, (_, index) => ({
  value: String(index),
  label: `${index} decimal place${index === 1 ? "" : "s"}`,
}))

const FILENAME_PATTERN_OPTIONS = [
  { value: "<report>_<scope>_<date>", label: "report_scope_date" },
  { value: "<report>_<date>", label: "report_date" },
  { value: "<report>_<scope>", label: "report_scope" },
]

const SCOPE_OPTIONS = [
  { value: "current_term", label: "Current term" },
  { value: "all", label: "All data" },
  { value: "previous_term", label: "Previous term" },
]

export function ExportSection({ settings }: { settings: FacultySettingsResponse }) {
  const [prefs, setPrefs] = React.useState<ExportPrefs>(() => readExport(settings))
  const { saving, saved, error, apply } = useSettingsSection("export")

  async function patch(patch: ExportPatch) {
    const result = await apply(patch)
    if (result) setPrefs(readExport(result))
  }

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <SectionStatus
        saving={saving}
        saved={saved}
        savedMessage="Export preferences updated."
        error={error}
      />

      <PreferenceSection
        icon={FileType}
        title="CSV format"
        description="How generated CSV files are structured."
      >
        <div className="flex flex-col gap-5 sm:flex-row sm:flex-wrap">
          <SelectField
            id="ex-delimiter"
            label="Delimiter"
            value={prefs.delimiter}
            options={DELIMITER_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ delimiter: value })}
          />
          <SelectField
            id="ex-date"
            label="Date format"
            value={prefs.date_format}
            options={DATE_FORMAT_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ date_format: value })}
          />
          <SelectField
            id="ex-time"
            label="Time format"
            value={prefs.time_format}
            options={TIME_FORMAT_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ time_format: value })}
          />
          <SelectField
            id="ex-precision"
            label="Decimal precision"
            value={prefs.decimal_precision}
            options={PRECISION_OPTIONS}
            disabled={saving}
            onValueChange={(value) =>
              value && void patch({ decimal_precision: Number.parseInt(value, 10) })
            }
          />
        </div>
        <div className="mt-2">
          <SwitchRow
            id="ex-bom"
            label="UTF-8 with BOM"
            description="Add a byte-order mark so Excel opens files correctly."
            checked={prefs.encoding_with_bom}
            disabled={saving}
            onCheckedChange={(checked) => void patch({ encoding_with_bom: checked })}
          />
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={FileDown}
        title="File names and scope"
        description="Naming and default data scope for exports."
      >
        <div className="flex flex-col gap-5 sm:flex-row sm:flex-wrap">
          <SelectField
            id="ex-pattern"
            label="File name pattern"
            value={prefs.filename_pattern}
            options={FILENAME_PATTERN_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ filename_pattern: value })}
          />
          <SelectField
            id="ex-scope"
            label="Default scope"
            value={prefs.default_scope}
            options={SCOPE_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ default_scope: value })}
          />
          <TextField
            id="ex-timezone"
            label="Timezone"
            value={prefs.timezone}
            maxLength={40}
            disabled={saving}
            onCommit={(value) => void patch({ timezone: value })}
          />
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={Tags}
        title="Export templates"
        description="Saved export configurations for one-click generation."
      >
        <p className="text-sm text-muted-foreground">
          Export templates are managed from the export actions on analytics pages.
        </p>
      </PreferenceSection>
    </div>
  )
}
