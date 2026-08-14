import { DICTIONARIES } from "./dictionaries.ts"
import type { SupportedLanguage } from "./types.ts"

export function translate(
  key: string,
  lang: SupportedLanguage = "en",
  defaultText?: string,
): string {
  if (!key) return ""
  const dict = DICTIONARIES[lang]
  if (dict && dict[key] !== undefined) {
    return dict[key]
  }
  const enDict = DICTIONARIES["en"]
  if (enDict && enDict[key] !== undefined) {
    return enDict[key]
  }
  return defaultText !== undefined ? defaultText : key
}
