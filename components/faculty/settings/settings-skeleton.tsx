import { Skeleton } from "@/components/ui/skeleton"

export function SettingsSectionSkeleton() {
  return (
    <div
      className="flex flex-col gap-4"
      aria-label="Loading settings section"
      role="status"
    >
      <Skeleton className="h-24 rounded-xl" />
      <Skeleton className="h-56 rounded-xl" />
      <Skeleton className="h-56 rounded-xl" />
    </div>
  )
}
