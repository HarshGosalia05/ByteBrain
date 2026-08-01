import { cn } from "@/lib/utils"

export function AvatarInitials({
  firstName,
  lastName,
  className,
}: {
  firstName: string
  lastName: string
  className?: string
}) {
  const initials = `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase()
  return (
    <span
      className={cn(
        "inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary",
        className,
      )}
      aria-hidden="true"
    >
      {initials}
    </span>
  )
}
