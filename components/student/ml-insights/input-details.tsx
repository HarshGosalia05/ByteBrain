import { ChevronDown } from "lucide-react"

import type { MlExplanationInput } from "@/lib/student-api"

function readableName(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function formatValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No"
  if (value === null || value === undefined) return "Not available"
  return String(value)
}

export function InputDetails({ inputs }: { inputs: MlExplanationInput[] }) {
  if (inputs.length === 0) return null
  return (
    <details className="group">
      <summary className="flex w-fit cursor-pointer list-none items-center gap-1 text-xs font-medium text-muted-foreground outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
        <ChevronDown
          className="size-3.5 transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
        Inputs used
      </summary>
      <div className="mt-3 flex flex-wrap gap-2">
        {inputs.map((input, index) => (
          <span
            key={index}
            className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground"
          >
            <span className="min-w-0 truncate">{readableName(input.name)}</span>
            <span
              className={`font-medium tabular-nums ${input.present ? "text-foreground" : ""}`}
            >
              {input.present ? formatValue(input.value) : "Not available"}
            </span>
          </span>
        ))}
      </div>
    </details>
  )
}
