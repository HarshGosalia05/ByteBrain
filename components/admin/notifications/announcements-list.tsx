import { Bell, Users, UserCog, Megaphone } from "lucide-react"

import type { AdminAnnouncementItem } from "@/lib/admin-api"
import { ChartCard } from "@/components/shared/data/chart-card"

export function AnnouncementsList({ announcements }: { announcements: AdminAnnouncementItem[] }) {
  return (
    <ChartCard
      title="Sent Announcements & Notices"
      subtitle="History of admin broadcast notifications"
      status={announcements.length > 0 ? "ready" : "empty"}
      emptyIcon={Bell}
      emptyTitle="No sent announcements"
      emptyDescription="Broadcast announcements created by admin will appear here."
    >
      <div className="flex flex-col gap-3">
        {announcements.map((item, idx) => (
          <div
            key={idx}
            className="flex flex-col gap-2 rounded-lg border border-border/60 bg-card p-3.5 text-xs transition-colors hover:bg-muted/30"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm">{item.title}</span>
                <span className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground uppercase">
                  {item.type.replace("_", " ")}
                </span>
                {item.priority === "Urgent" || item.priority === "High" ? (
                  <span className="inline-flex items-center rounded-md bg-destructive/10 text-destructive px-2 py-0.5 text-xs font-medium">
                    {item.priority}
                  </span>
                ) : null}
              </div>
              <span className="text-muted-foreground text-[11px]">
                {item.created_at ? new Date(item.created_at).toLocaleString() : "Just now"}
              </span>
            </div>

            <p className="text-muted-foreground whitespace-pre-wrap">{item.message}</p>

            <div className="flex flex-wrap items-center gap-3 pt-1 border-t border-border/40 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1 font-medium text-foreground">
                <Megaphone className="size-3 text-primary" />
                Audience: <span className="capitalize">{item.target_audience}</span>
              </span>
              <span className="flex items-center gap-1">
                {item.target_audience === "faculty" ? (
                  <UserCog className="size-3" />
                ) : (
                  <Users className="size-3" />
                )}
                {item.recipient_count} recipient{item.recipient_count === 1 ? "" : "s"} notified
              </span>
            </div>
          </div>
        ))}
      </div>
    </ChartCard>
  )
}
