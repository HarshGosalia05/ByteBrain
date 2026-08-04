import type { BffResult } from "@/lib/faculty-api"

export type SectionResult<T> = {
  data: T | null
  error: string | null
}

export function toSectionResult<T>(
  result: PromiseSettledResult<BffResult<T>> | BffResult<T>,
): SectionResult<T> {
  if ("status" in result) {
    if (result.status === "rejected") {
      return { data: null, error: "Something went wrong while loading this section." }
    }
    if (!result.value.ok) {
      return { data: null, error: result.value.error.message }
    }
    return { data: result.value.data, error: null }
  }
  if (!result.ok) {
    return { data: null, error: result.error.message }
  }
  return { data: result.data, error: null }
}
