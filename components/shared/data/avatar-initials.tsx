import { cn } from "@/lib/utils"

const sizeStyles = {
  sm: "size-8 text-xs",
  md: "size-10 text-sm",
  lg: "size-14 text-lg",
} as const

export function AvatarInitials({
  firstName,
  lastName,
  size = "sm",
  className,
}: {
  firstName: string
  lastName: string
  size?: keyof typeof sizeStyles
  className?: string
}) {
  const first = firstName?.trim() ? firstName.charAt(0) : "S"
  const last = lastName?.trim() ? lastName.charAt(0) : "T"
  const initials = `${first}${last}`.toUpperCase()
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full bg-primary/10 font-semibold tracking-wide text-primary select-none",
        sizeStyles[size],
        className,
      )}
      aria-hidden="true"
    >
      {initials}
    </span>
  )
}
