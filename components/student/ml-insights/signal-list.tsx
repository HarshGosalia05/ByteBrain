import type { MlExplanationInput } from "@/lib/student-api"

const SIGNAL_LABELS: Record<string, string> = {
  semester_percentage: "Current Semester %",
  semester_sgpa: "Current SGPA",
  semester_attendance_percentage: "Attendance",
  backlog_count: "Backlogs",
  semester_result: "Semester Result",
}

const NUMERIC_SIGNALS = new Set([
  "semester_percentage",
  "semester_sgpa",
  "semester_attendance_percentage",
  "backlog_count",
])

function humanize(name: string): string {
  return name
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

function formatValue(input: MlExplanationInput): string {
  if (!NUMERIC_SIGNALS.has(input.name)) return String(input.value)
  const num = Number(input.value)
  if (Number.isNaN(num)) return String(input.value)
  if (input.name === "backlog_count") return String(Math.round(num))
  if (input.name === "semester_sgpa") return num.toFixed(2)
  return `${num.toFixed(1)}%`
}

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold tracking-widest text-muted-foreground uppercase">
      {children}
    </p>
  )
}

export function SignalGrid({ inputs }: { inputs: MlExplanationInput[] }) {
  const visible = inputs.filter((input) => input.present)
  if (visible.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Academic signals will appear here once your results are recorded.
      </p>
    )
  }
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {visible.map((input, index) => (
        <div
          key={`${input.name}-${index}`}
          className="rounded-lg border border-foreground/10 bg-background/40 px-3 py-2"
        >
          <p className="text-[0.6875rem] font-medium tracking-wide text-muted-foreground uppercase">
            {SIGNAL_LABELS[input.name] ?? humanize(input.name)}
          </p>
          <p className="mt-0.5 text-sm font-semibold tabular-nums">
            {formatValue(input)}
          </p>
        </div>
      ))}
    </div>
  )
}
