"use client"

import { useRouter } from "next/navigation"

import { ErrorState } from "@/components/shared/state/error-state"

type ErrorStateWithRetryProps = {
  title?: string
  description?: string
  className?: string
}

export function ErrorStateWithRetry({
  title,
  description,
  className,
}: ErrorStateWithRetryProps) {
  const router = useRouter()

  return (
    <ErrorState
      title={title}
      description={description}
      className={className}
      onRetry={() => router.refresh()}
    />
  )
}