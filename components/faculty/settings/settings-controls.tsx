"use client"

import * as React from "react"
import { CheckCircle2, LoaderCircle, TriangleAlert } from "lucide-react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectIcon,
  SelectItem,
  SelectList,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { FacultySettingsResponse } from "@/lib/faculty-api"

export type SelectOption = { value: string; label: string }

export function SelectField({
  id,
  label,
  description,
  value,
  options,
  disabled,
  onValueChange,
}: {
  id: string
  label: string
  description?: string
  value: string
  options: SelectOption[]
  disabled: boolean
  onValueChange: (value: string | null) => void
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
      <Select id={id} value={value} onValueChange={onValueChange} disabled={disabled}>
        <SelectTrigger className="w-full sm:w-56">
          <SelectValue>
            {(selected: string | null) =>
              options.find((option) => option.value === selected)?.label ?? ""
            }
          </SelectValue>
          <SelectIcon />
        </SelectTrigger>
        <SelectContent>
          <SelectList>
            {options.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectList>
        </SelectContent>
      </Select>
    </div>
  )
}

export function SwitchRow({
  id,
  label,
  description,
  checked,
  disabled,
  onCheckedChange,
}: {
  id: string
  label: string
  description: string
  checked: boolean
  disabled: boolean
  onCheckedChange: (checked: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border/60 py-3.5 last:border-0">
      <div className="flex min-w-0 flex-col gap-0.5">
        <Label htmlFor={id} className="cursor-pointer">
          {label}
        </Label>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <Switch
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        className="shrink-0"
      />
    </div>
  )
}

export function TextField({
  id,
  label,
  description,
  value,
  type = "text",
  maxLength,
  placeholder,
  disabled,
  onCommit,
}: {
  id: string
  label: string
  description?: string
  value: string
  type?: string
  maxLength?: number
  placeholder?: string
  disabled: boolean
  onCommit: (value: string) => void
}) {
  const [draft, setDraft] = React.useState(value)
  const [previousValue, setPreviousValue] = React.useState(value)

  if (previousValue !== value) {
    setPreviousValue(value)
    setDraft(value)
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
      <Input
        id={id}
        type={type}
        value={draft}
        maxLength={maxLength}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => {
          const next = draft.trim()
          if (next !== value) onCommit(next)
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur()
        }}
        className="w-full sm:w-56"
      />
    </div>
  )
}

export function NumberField({
  id,
  label,
  description,
  value,
  min,
  max,
  disabled,
  onCommit,
}: {
  id: string
  label: string
  description?: string
  value: number | null
  min: number
  max: number
  disabled: boolean
  onCommit: (value: number | null) => void
}) {
  const [draft, setDraft] = React.useState(value === null ? "" : String(value))
  const [invalid, setInvalid] = React.useState(false)
  const [previous, setPrevious] = React.useState(value)

  if (previous !== value) {
    setPrevious(value)
    setDraft(value === null ? "" : String(value))
  }

  function commit() {
    const trimmed = draft.trim()
    if (trimmed === "") {
      setInvalid(false)
      onCommit(null)
      return
    }
    const parsed = Number(trimmed)
    if (!Number.isFinite(parsed)) {
      setInvalid(true)
      return
    }
    setInvalid(false)
    onCommit(parsed)
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
      <Input
        id={id}
        inputMode="decimal"
        value={draft}
        placeholder="Admin default"
        disabled={disabled}
        aria-invalid={invalid}
        onChange={(event) => {
          setDraft(event.target.value)
          setInvalid(false)
        }}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur()
        }}
        className="w-full sm:w-40"
      />
      <p className="text-xs text-muted-foreground">
        Admin range: {min}–{max}. Leave empty to use the default.
      </p>
      {invalid && <p className="text-xs text-destructive">Enter a valid number.</p>}
    </div>
  )
}

export function SectionStatus({
  saving,
  saved,
  savedMessage,
  error,
}: {
  saving: boolean
  saved: boolean
  savedMessage: string
  error: string | null
}) {
  if (saving) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
        <LoaderCircle className="size-4 animate-spin" />
        Saving your preferences…
      </p>
    )
  }
  if (saved) {
    return (
      <p className="flex items-center gap-1.5 text-sm text-chart-2" role="status">
        <CheckCircle2 className="size-4 shrink-0" />
        {savedMessage}
      </p>
    )
  }
  if (error) {
    return (
      <p className="flex items-center gap-1.5 text-sm text-destructive" role="alert">
        <TriangleAlert className="size-4 shrink-0" />
        {error}
      </p>
    )
  }
  return null
}

export function useSettingsSection(namespace: string) {
  const [saving, setSaving] = React.useState(false)
  const [saved, setSaved] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const timer = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  React.useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [])

  async function apply(
    patch: Record<string, unknown>,
  ): Promise<FacultySettingsResponse | null> {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const res = await fetch(`/api/faculty/settings/${namespace}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
        cache: "no-store",
      })
      const result = (await res.json()) as
        | { ok: true; data: FacultySettingsResponse }
        | { ok: false; error: { message: string } }
      if (!result.ok) {
        setError(result.error.message)
        return null
      }
      setSaved(true)
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => setSaved(false), 3000)
      return result.data
    } catch {
      setError("Could not update your preferences. Please try again.")
      return null
    } finally {
      setSaving(false)
    }
  }

  return { saving, saved, error, apply }
}
