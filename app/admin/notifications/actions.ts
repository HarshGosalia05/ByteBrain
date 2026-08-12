"use server"

import {
  createAnnouncement,
  type CreateAnnouncementInput,
  type CreateAnnouncementResult,
  type BffResult,
} from "@/lib/admin-api"

export async function broadcastAnnouncementAction(
  input: CreateAnnouncementInput,
): Promise<BffResult<CreateAnnouncementResult>> {
  return createAnnouncement(input)
}
