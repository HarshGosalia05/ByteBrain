"use client"

import * as React from "react"
import { translate } from "./translate.ts"
import type { LanguageContextType, SupportedLanguage } from "./types.ts"

const LANGUAGE_STORAGE_KEY = "bytebrain_display_language"

const LanguageContext = React.createContext<LanguageContextType>({
  language: "en",
  setLanguage: async () => {},
  t: (key: string, defaultText?: string) => defaultText ?? key,
})

export { translate }

export function LanguageProvider({
  children,
  initialLanguage = "en",
}: {
  children: React.ReactNode
  initialLanguage?: SupportedLanguage
}) {
  const [language, setLanguageState] = React.useState<SupportedLanguage>(initialLanguage)

  // Hydrate language preference from localStorage if available
  React.useEffect(() => {
    try {
      const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY) as SupportedLanguage | null
      if (stored && (stored === "en" || stored === "hi" || stored === "gu")) {
        setLanguageState(stored)
      }
    } catch {
      // localStorage is not accessible in restricted environments
    }

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === LANGUAGE_STORAGE_KEY && e.newValue) {
        const val = e.newValue as SupportedLanguage
        if (val === "en" || val === "hi" || val === "gu") {
          setLanguageState(val)
        }
      }
    }

    const handleCustomChange = (e: Event) => {
      const customEvent = e as CustomEvent<SupportedLanguage>
      if (customEvent.detail && (customEvent.detail === "en" || customEvent.detail === "hi" || customEvent.detail === "gu")) {
        setLanguageState(customEvent.detail)
      }
    }

    window.addEventListener("storage", handleStorageChange)
    window.addEventListener("bytebrain-language-changed", handleCustomChange)
    return () => {
      window.removeEventListener("storage", handleStorageChange)
      window.removeEventListener("bytebrain-language-changed", handleCustomChange)
    }
  }, [])

  const setLanguage = React.useCallback(async (newLang: SupportedLanguage) => {
    if (newLang !== "en" && newLang !== "hi" && newLang !== "gu") return

    setLanguageState(newLang)
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, newLang)
    } catch {
      // ignore
    }

    // Notify all listeners in this window
    window.dispatchEvent(
      new CustomEvent<SupportedLanguage>("bytebrain-language-changed", {
        detail: newLang,
      }),
    )

    // Persist to user settings API in background
    try {
      await fetch("/api/student/settings/account", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_language: newLang }),
      })
    } catch {
      // Best effort backend sync
    }
  }, [])

  const t = React.useCallback(
    (key: string, defaultText?: string): string => {
      return translate(key, language, defaultText)
    },
    [language],
  )

  const value = React.useMemo(
    () => ({
      language,
      setLanguage,
      t,
    }),
    [language, setLanguage, t],
  )

  return (
    <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
  )
}

export function useTranslation() {
  return React.useContext(LanguageContext)
}
