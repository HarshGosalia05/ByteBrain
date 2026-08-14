export type SupportedLanguage = "en" | "hi" | "gu"

export type TranslationDictionary = Record<string, string>

export type LanguageContextType = {
  language: SupportedLanguage
  setLanguage: (lang: SupportedLanguage) => Promise<void>
  t: (key: string, defaultText?: string) => string
}
