"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { cn } from "@/lib/utils"

export function SemesterSelect({
  semesters,
  current,
}: {
  semesters: number[]
  current: number
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const selected = Number(searchParams.get("semester") ?? current)

  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by semester">
      <button
        type="button"
        onClick={() => router.push(pathname)}
        aria-pressed={!searchParams.get("semester")}
        className={cn(
          "flex min-h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          !searchParams.get("semester")
            ? "border-primary bg-primary text-primary-foreground"
            : "border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground",
        )}
      >
        Current
      </button>
      {semesters.map((semester) => (
        <button
          key={semester}
          type="button"
          onClick={() => router.push(`${pathname}?semester=${semester}`)}
          aria-pressed={selected === semester}
          className={cn(
            "flex min-h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
            selected === semester
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
        >
          Sem {semester}
        </button>
      ))}
    </div>
  )
}
