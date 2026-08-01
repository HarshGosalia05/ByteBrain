"use client"

import { useState } from "react"
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type Column,
  type SortingState,
} from "@tanstack/react-table"
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react"

import type { SubjectPerformanceItem } from "@/lib/student-api"

import { GradeBadge } from "@/components/shared/data/grade-badge"
import { cn } from "@/lib/utils"

const columnHelper = createColumnHelper<SubjectPerformanceItem>()

const columns = [
  columnHelper.accessor("semester", {
    header: "Semester",
    cell: (info) => `Sem ${info.getValue()}`,
  }),
  columnHelper.accessor("subject_code", {
    header: "Code",
    cell: (info) => (
      <span className="font-mono text-xs text-muted-foreground">{info.getValue()}</span>
    ),
  }),
  columnHelper.accessor("subject_name", {
    header: "Subject",
    cell: (info) => <span className="font-medium">{info.getValue()}</span>,
  }),
  columnHelper.accessor("internal_marks", {
    header: "Internal",
    cell: (info) =>
      info.getValue() !== null ? info.getValue()!.toFixed(1) : <span className="text-muted-foreground">—</span>,
  }),
  columnHelper.accessor("external_marks", {
    header: "External",
    cell: (info) =>
      info.getValue() !== null ? info.getValue()!.toFixed(1) : <span className="text-muted-foreground">—</span>,
  }),
  columnHelper.accessor("total_marks", {
    header: "Total",
    cell: (info) =>
      info.getValue() !== null ? info.getValue()!.toFixed(1) : <span className="text-muted-foreground">—</span>,
  }),
  columnHelper.accessor("grade", {
    header: "Grade",
    cell: (info) => <GradeBadge grade={info.getValue()} />,
  }),
  columnHelper.accessor("attendance_percentage", {
    header: "Attendance %",
    cell: (info) =>
      info.getValue() !== null
        ? `${info.getValue()!.toFixed(1)}%`
        : <span className="text-muted-foreground">—</span>,
  }),
]

function SortHeader({ column }: { column: Column<SubjectPerformanceItem, unknown> }) {
  const isSorted = column.getIsSorted()
  const label =
    typeof column.columnDef.header === "string" ? column.columnDef.header : ""
  return (
    <button
      type="button"
      onClick={column.getToggleSortingHandler()}
      className="flex items-center gap-1 hover:text-foreground"
    >
      {label}
      {isSorted === "asc" ? (
        <ArrowUp className="size-3" />
      ) : isSorted === "desc" ? (
        <ArrowDown className="size-3" />
      ) : (
        <ChevronsUpDown className="size-3 opacity-50" />
      )}
    </button>
  )
}

export function SubjectTable({ rows }: { rows: SubjectPerformanceItem[] }) {
  const [sorting, setSorting] = useState<SortingState>([])

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">Subject performance</caption>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} className="border-b text-left text-xs text-muted-foreground">
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  scope="col"
                  aria-sort={header.column.getIsSorted() === "asc" ? "ascending" : header.column.getIsSorted() === "desc" ? "descending" : undefined}
                  className={cn(
                    "py-3 pr-4 font-medium first:pl-4",
                    header.column.id === "total_marks" ||
                      header.column.id === "internal_marks" ||
                      header.column.id === "external_marks" ||
                      header.column.id === "attendance_percentage"
                      ? "text-right"
                      : "",
                  )}
                >
                  <SortHeader column={header.column} />
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="border-b last:border-0">
              {row.getVisibleCells().map((cell) => (
                <td
                  key={cell.id}
                  className={cn(
                    "py-2.5 pr-4 first:pl-4",
                    cell.column.id === "total_marks" ||
                      cell.column.id === "internal_marks" ||
                      cell.column.id === "external_marks" ||
                      cell.column.id === "attendance_percentage"
                      ? "text-right"
                      : "",
                  )}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
