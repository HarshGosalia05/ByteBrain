import { cn } from "@/lib/utils"

import { FreshnessBadge } from "@/components/shared/data/freshness-badge"

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
  return (
    <div className={cn("flex flex-col gap-1", className)} {...props}>
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        <FreshnessBadge fetchedAt={fetchedAt} />
      </div>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
    </div>
  )
}
