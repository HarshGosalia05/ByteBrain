"use client"

import * as React from "react"
import { Eye, Hand, Wand2 } from "lucide-react"

import type { FacultySettingsResponse } from "@/lib/faculty-api"

import { PreferenceSection } from "./preference-section"
import {
  SectionStatus,
  SelectField,
  SwitchRow,
  useSettingsSection,
} from "./settings-controls"

type AccessibilityPrefs = {
  high_contrast: boolean
  color_blind_palette: string
  font_scale: string
  reduced_motion: boolean
  focus_ring_size: string
  keyboard_navigation: boolean
  screen_reader_labels: boolean
  preset: string
}

const DEFAULTS: AccessibilityPrefs = {
  high_contrast: false,
  color_blind_palette: "none",
  font_scale: "default",
  reduced_motion: false,
  focus_ring_size: "default",
  keyboard_navigation: true,
  screen_reader_labels: true,
  preset: "none",
}

function readAccessibility(settings: FacultySettingsResponse): AccessibilityPrefs {
  const a = settings.namespaces.accessibility ?? {}
  const pickBool = (key: "high_contrast" | "reduced_motion" | "keyboard_navigation" | "screen_reader_labels"): boolean =>
    typeof a[key] === "boolean" ? (a[key] as boolean) : DEFAULTS[key]
  const pickString = (key: "color_blind_palette" | "font_scale" | "focus_ring_size" | "preset"): string =>
    typeof a[key] === "string" ? (a[key] as string) : DEFAULTS[key]
  return {
    high_contrast: pickBool("high_contrast"),
    color_blind_palette: pickString("color_blind_palette"),
    font_scale: pickString("font_scale"),
    reduced_motion: pickBool("reduced_motion"),
    focus_ring_size: pickString("focus_ring_size"),
    keyboard_navigation: pickBool("keyboard_navigation"),
    screen_reader_labels: pickBool("screen_reader_labels"),
    preset: pickString("preset"),
  }
}

const PALETTE_OPTIONS = [
  { value: "none", label: "No filter" },
  { value: "protanopia", label: "Protanopia" },
  { value: "deuteranopia", label: "Deuteranopia" },
  { value: "tritanopia", label: "Tritanopia" },
]

const FONT_SCALE_OPTIONS = [
  { value: "default", label: "Default" },
  { value: "large", label: "Large" },
  { value: "x-large", label: "Extra large" },
]

const FOCUS_RING_OPTIONS = [
  { value: "default", label: "Default" },
  { value: "large", label: "Large" },
]

const PRESET_OPTIONS = [
  { value: "none", label: "No preset" },
  { value: "high_contrast", label: "High contrast" },
  { value: "large_text", label: "Large text" },
  { value: "reduce_motion", label: "Reduce motion" },
]

export function AccessibilitySection({ settings }: { settings: FacultySettingsResponse }) {
  const [prefs, setPrefs] = React.useState<AccessibilityPrefs>(() =>
    readAccessibility(settings),
  )
  const { saving, saved, error, apply } = useSettingsSection("accessibility")

  async function patch(patch: Record<string, unknown>) {
    const result = await apply(patch)
    if (result) setPrefs(readAccessibility(result))
  }

  function applyPreset(preset: string | null) {
    if (!preset) return
    const presets: Record<string, Record<string, unknown>> = {
      none: { preset: "none" },
      high_contrast: { preset: "high_contrast", high_contrast: true },
      large_text: { preset: "large_text", font_scale: "large" },
      reduce_motion: { preset: "reduce_motion", reduced_motion: true },
    }
    void patch(presets[preset] ?? { preset })
  }

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <SectionStatus
        saving={saving}
        saved={saved}
        savedMessage="Accessibility preferences updated."
        error={error}
      />

      <PreferenceSection
        icon={Wand2}
        title="Presets"
        description="One-click combinations of accessibility settings."
      >
        <SelectField
          id="ac-preset"
          label="Accessibility preset"
          value={prefs.preset}
          options={PRESET_OPTIONS}
          disabled={saving}
          onValueChange={(value) => void applyPreset(value)}
        />
      </PreferenceSection>

      <PreferenceSection
        icon={Eye}
        title="Visual"
        description="Contrast, colour and text size."
      >
        <SwitchRow
          id="ac-contrast"
          label="High contrast"
          description="Increase contrast between text and backgrounds."
          checked={prefs.high_contrast}
          disabled={saving}
          onCheckedChange={(checked) => void patch({ high_contrast: checked })}
        />
        <div className="flex flex-col gap-5 pt-3 sm:flex-row sm:flex-wrap">
          <SelectField
            id="ac-palette"
            label="Colour-blind palette"
            value={prefs.color_blind_palette}
            options={PALETTE_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ color_blind_palette: value })}
          />
          <SelectField
            id="ac-font"
            label="Text size"
            value={prefs.font_scale}
            options={FONT_SCALE_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ font_scale: value })}
          />
        </div>
      </PreferenceSection>

      <PreferenceSection
        icon={Hand}
        title="Motion and interaction"
        description="Animation, focus and navigation support."
      >
        <SwitchRow
          id="ac-motion"
          label="Reduce motion"
          description="Minimise animations and transitions."
          checked={prefs.reduced_motion}
          disabled={saving}
          onCheckedChange={(checked) => void patch({ reduced_motion: checked })}
        />
        <div className="pt-3">
          <SelectField
            id="ac-focus"
            label="Focus ring size"
            value={prefs.focus_ring_size}
            options={FOCUS_RING_OPTIONS}
            disabled={saving}
            onValueChange={(value) => value && void patch({ focus_ring_size: value })}
          />
        </div>
        <div className="mt-2">
          <SwitchRow
            id="ac-keyboard"
            label="Keyboard navigation"
            description="Full navigation using only the keyboard."
            checked={prefs.keyboard_navigation}
            disabled={saving}
            onCheckedChange={(checked) => void patch({ keyboard_navigation: checked })}
          />
          <SwitchRow
            id="ac-sr"
            label="Screen-reader labels"
            description="Expose extra descriptive labels to assistive technology."
            checked={prefs.screen_reader_labels}
            disabled={saving}
            onCheckedChange={(checked) => void patch({ screen_reader_labels: checked })}
          />
        </div>
      </PreferenceSection>
    </div>
  )
}
