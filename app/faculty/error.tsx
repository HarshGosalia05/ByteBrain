"use client"

import { ErrorState } from "@/components/shared/state/error-state"

export default function Error({
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <ErrorState
        title="We couldn't load this page"
        description="Please try again. If the problem persists, sign out and back in."
        onRetry={() => reset()}
      />
    </div>
  )
}
