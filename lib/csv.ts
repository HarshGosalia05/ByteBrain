export type CsvColumn = {
  key: string
  label: string
}

function escapeCell(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value)
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`
  }
  return text
}

export function toCsv(
  columns: CsvColumn[],
  rows: Array<Record<string, unknown>>,
): string {
  const header = columns.map((c) => escapeCell(c.label)).join(",")
  const body = rows.map((row) => columns.map((c) => escapeCell(row[c.key])).join(","))
  return [header, ...body].join("\r\n")
}

export function scopeStamp(parts: Array<string | null | undefined>): string {
  const clean = parts.filter((p): p is string => Boolean(p)).join("_") || "all"
  return clean.replace(/[^a-z0-9_]/gi, "")
}
