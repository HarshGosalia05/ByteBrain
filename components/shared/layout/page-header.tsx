"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { FreshnessBadge } from "@/components/shared/data/freshness-badge"
import { useTranslation } from "@/lib/i18n"

type PageHeaderProps = React.ComponentProps<"div"> & {
  title: string
  description?: string
  fetchedAt?: string | null
}

export function PageHeader({
  title,
  description,
  fetchedAt,
  className,
  ...props
}: PageHeaderProps) {
  const { t } = useTranslation()

  return (
    <div className={cn("flex flex-col gap-2", className)} {...props}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">{t(title)}</h1>
        <FreshnessBadge fetchedAt={fetchedAt} />
      </div>
      {description && <p className="text-sm text-muted-foreground">{t(description)}</p>}
    </div>
  )
}
