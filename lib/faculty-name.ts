export function splitFullName(fullName: string | null | undefined): {
  first: string
  last: string
} {
  const parts = (fullName ?? "").trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return { first: "", last: "" }
  if (parts.length === 1) return { first: parts[0], last: "" }
  return { first: parts[0], last: parts[parts.length - 1] }
}
