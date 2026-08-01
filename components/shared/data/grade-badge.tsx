import { Badge } from "@/components/ui/badge"

export function GradeBadge({ grade }: { grade: string | null }) {
  if (!grade) {
    return <Badge variant="muted">—</Badge>
  }
  return <Badge variant="secondary">{grade}</Badge>
}
