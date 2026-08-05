"use client"

import { Download } from "lucide-react"

import { toCsv, type CsvColumn } from "@/lib/csv"

type ExportButtonProps = {
  fileName: string
  columns: CsvColumn[]
  rows: Array<Record<string, unknown>>
  label?: string
}

export function ExportButton({ fileName, columns, rows, label = "CSV" }: ExportButtonProps) {
  const handleExport = () => {
    const csv = toCsv(columns, rows)
    const blob = new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8;" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    const base = fileName.endsWith(".csv") ? fileName.slice(0, -4) : fileName
    link.download = `${base}_${Date.now()}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  return (
    <button
      type="button"
      onClick={handleExport}
      className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground print:hidden"
    >
      <Download className="size-3.5" />
      {label}
    </button>
  )
}
