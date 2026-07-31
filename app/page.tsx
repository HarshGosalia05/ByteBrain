import { redirectBySession } from "@/lib/session"

export default async function Page() {
  await redirectBySession()

  return null
}
