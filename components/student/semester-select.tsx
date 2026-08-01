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
    <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Filter by semester">
      <button
        type="button"
        onClick={() => router.push(pathname)}
        className={cn(
          "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
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
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
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
