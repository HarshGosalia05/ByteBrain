import { Suspense } from "react"

import { LoadingSkeleton } from "@/components/shared/state/loading-skeleton"

export function SectionSuspense({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<LoadingSkeleton />}>{children}</Suspense>
}
