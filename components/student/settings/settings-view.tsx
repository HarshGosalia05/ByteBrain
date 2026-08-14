"use client"

import * as React from "react"
import { useTheme } from "next-themes"
import {
  AlertCircle,
  Bell,
  Check,
  CheckCircle2,
  Globe,
  KeyRound,
  Loader2,
  Lock,
  LogOut,
  Monitor,
  Moon,
  Palette,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  Sun,
  UserRound,
  type LucideIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"
import { signOut } from "@/lib/auth-actions"
import { useTranslation, type SupportedLanguage } from "@/lib/i18n"
import type { StudentSettingsResponse } from "@/lib/student-api"

const THEME_OPTIONS: { value: string; label: string; icon: LucideIcon }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
]

const LANGUAGE_OPTIONS: { value: SupportedLanguage; label: string; native: string }[] = [
  { value: "en", label: "English (US)", native: "English" },
  { value: "hi", label: "Hindi", native: "हिन्दी" },
  { value: "gu", label: "Gujarati", native: "ગુજરાતી" },
]

const NAME_DISPLAY_OPTIONS = [
  { value: "full_name", label: "Full name", example: "Aarav Patel" },
  { value: "first_name", label: "First name only", example: "Aarav" },
  { value: "formal", label: "Formal (Last, First)", example: "Patel, Aarav" },
  { value: "with_id", label: "With Student ID", example: "Aarav Patel (2023010002)" },
]

function SectionCard({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: LucideIcon
  title: string
  description: string
  children: React.ReactNode
}) {
  const { t } = useTranslation()

  return (
    <section className="rounded-xl bg-card ring-1 ring-foreground/10">
      <div className="flex items-start gap-3 border-b border-border/60 p-5">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Icon className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-semibold">{t(title)}</h2>
          <p className="text-xs text-muted-foreground">{t(description)}</p>
        </div>
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

export function SettingsView({
  session,
  initialSettings,
}: {
  session: {
    username: string | null
    role: string | null
    studentId: string | null
    department: string | null
  } | null
  initialSettings?: StudentSettingsResponse | null
}) {
  const { theme, setTheme } = useTheme()
  const { language, setLanguage, t } = useTranslation()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  // --- State from persisted settings ---
  const [settings, setSettings] = React.useState<StudentSettingsResponse["namespaces"]>(
    initialSettings?.namespaces ?? {
      account: {
        display_language: "en",
        name_display: "full_name",
      },
      notifications: {
        grade_alerts: true,
        attendance_warnings: true,
        semester_results: true,
      },
      security: {
        two_factor_enabled: false,
        two_factor_method: "none",
        password_updated_at: "",
        last_sign_out_all: "",
      },
    },
  )

  // Status banners & feedback
  const [savingKey, setSavingKey] = React.useState<string | null>(null)
  const [feedback, setFeedback] = React.useState<{ type: "success" | "error"; message: string } | null>(null)

  // Password change state
  const [currentPassword, setCurrentPassword] = React.useState("")
  const [newPassword, setNewPassword] = React.useState("")
  const [confirmPassword, setConfirmPassword] = React.useState("")
  const [passwordError, setPasswordError] = React.useState<string | null>(null)
  const [passwordSuccess, setPasswordSuccess] = React.useState<string | null>(null)
  const [isChangingPassword, setIsChangingPassword] = React.useState(false)

  // Sign out all devices state
  const [isSigningOutAll, setIsSigningOutAll] = React.useState(false)
  const [showSignOutConfirm, setShowSignOutConfirm] = React.useState(false)

  // --- API Mutators ---
  const updateNamespace = async (namespace: string, patch: Record<string, unknown>, keyDesc: string) => {
    setSavingKey(keyDesc)
    setFeedback(null)
    try {
      const res = await fetch(`/api/student/settings/${namespace}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      })
      const data = await res.json()
      if (res.ok && data.ok) {
        setSettings((prev) => ({
          ...prev,
          [namespace]: {
            ...prev[namespace],
            ...patch,
          },
        }))
        setFeedback({ type: "success", message: `${keyDesc} ${t("preference saved.", "saved.")}` })
      } else {
        const msg = data.error?.message || "Failed to save setting."
        setFeedback({ type: "error", message: msg })
      }
    } catch {
      setFeedback({ type: "error", message: "Network error saving setting." })
    } finally {
      setSavingKey(null)
    }
  }

  const handleLanguageChange = async (langValue: SupportedLanguage) => {
    setSavingKey("language")
    setFeedback(null)
    try {
      await setLanguage(langValue)
      setSettings((prev) => ({
        ...prev,
        account: {
          ...prev.account,
          display_language: langValue,
        },
      }))
      setFeedback({ type: "success", message: `${t("Display language")} ${t("preference saved.", "saved.")}` })
    } catch {
      setFeedback({ type: "error", message: "Failed to update language." })
    } finally {
      setSavingKey(null)
    }
  }

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault()
    setPasswordError(null)
    setPasswordSuccess(null)

    if (!currentPassword) {
      setPasswordError("Please enter your current password.")
      return
    }
    if (!newPassword || newPassword.length < 6) {
      setPasswordError("New password must be at least 6 characters.")
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirmation do not match.")
      return
    }
    if (newPassword === currentPassword) {
      setPasswordError("New password must be different from current password.")
      return
    }

    setIsChangingPassword(true)
    try {
      const res = await fetch("/api/student/settings/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      })
      const data = await res.json()
      if (res.ok && data.ok) {
        setPasswordSuccess(data.data?.message || "Password changed successfully.")
        setCurrentPassword("")
        setNewPassword("")
        setConfirmPassword("")
        if (data.data?.timestamp) {
          setSettings((prev) => ({
            ...prev,
            security: {
              ...prev.security,
              password_updated_at: data.data.timestamp,
            },
          }))
        }
      } else {
        setPasswordError(data.error?.message || "Failed to update password.")
      }
    } catch {
      setPasswordError("Connection error while updating password.")
    } finally {
      setIsChangingPassword(false)
    }
  }

  const handleToggleTwoFactor = async (checked: boolean) => {
    setSavingKey("two_factor")
    setFeedback(null)
    try {
      const res = await fetch("/api/student/settings/two-factor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: checked,
          method: checked ? "email" : "none",
        }),
      })
      const data = await res.json()
      if (res.ok && data.ok) {
        setSettings((prev) => ({
          ...prev,
          security: {
            ...prev.security,
            two_factor_enabled: checked,
            two_factor_method: checked ? "email" : "none",
            two_factor_updated_at: data.data?.timestamp ?? new Date().toISOString(),
          },
        }))
        setFeedback({
          type: "success",
          message: checked
            ? t("Two-factor authentication enabled via registered institutional email.")
            : t("Two-factor authentication disabled."),
        })
      } else {
        setFeedback({ type: "error", message: data.error?.message || "Failed to update 2FA." })
      }
    } catch {
      setFeedback({ type: "error", message: "Network error updating two-factor authentication." })
    } finally {
      setSavingKey(null)
    }
  }

  const handleSignOutAll = async () => {
    setIsSigningOutAll(true)
    try {
      await fetch("/api/student/settings/sign-out-all", { method: "POST" })
      await signOut()
    } catch {
      setIsSigningOutAll(false)
      setShowSignOutConfirm(false)
      setFeedback({ type: "error", message: "Failed to sign out all devices." })
    }
  }

  const accountPrefs = settings.account ?? {}
  const notifPrefs = settings.notifications ?? {}
  const secPrefs = settings.security ?? {}
  const activeLang = language || (accountPrefs.display_language as SupportedLanguage) || "en"

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      {feedback && (
        <div
          className={cn(
            "flex items-center gap-2.5 rounded-lg p-3 text-xs font-medium transition-all",
            feedback.type === "success"
              ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
              : "bg-destructive/10 text-destructive border border-destructive/20"
          )}
        >
          {feedback.type === "success" ? (
            <CheckCircle2 className="size-4 shrink-0" />
          ) : (
            <AlertCircle className="size-4 shrink-0" />
          )}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* 1. Theme Preference */}
      <SectionCard
        icon={Palette}
        title="Theme preference"
        description="Choose how the portal looks across this device."
      >
        <div className="grid grid-cols-3 gap-2 sm:max-w-md">
          {THEME_OPTIONS.map((option) => {
            const selected = mounted && theme === option.value
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setTheme(option.value)}
                aria-pressed={selected}
                className={cn(
                  "flex flex-col items-center gap-2 rounded-xl border px-3 py-3 text-sm font-medium transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring cursor-pointer",
                  selected
                    ? "border-primary bg-primary/5 text-foreground shadow-2xs"
                    : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <option.icon className="size-4" />
                {t(option.label)}
                {selected && <Check className="size-3 text-primary" />}
              </button>
            )
          })}
        </div>
      </SectionCard>

      {/* 2. Account Preferences: Display Language & Name Display */}
      <SectionCard
        icon={UserRound}
        title="Account preferences"
        description="Personalise your account and how information is displayed."
      >
        <div className="flex flex-col gap-6">
          {/* Display language */}
          <div className="flex flex-col gap-2.5 border-b border-border/60 pb-5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium flex items-center gap-1.5">
                  <Globe className="size-4 text-muted-foreground" />
                  {t("Display language")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("Select the language used for interface labels and natural language summaries.")}
                </p>
              </div>
              {savingKey === "language" && <Loader2 className="size-4 animate-spin text-muted-foreground" />}
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 sm:max-w-md pt-1">
              {LANGUAGE_OPTIONS.map((lang) => {
                const isSelected = activeLang === lang.value
                return (
                  <button
                    key={lang.value}
                    type="button"
                    onClick={() => handleLanguageChange(lang.value)}
                    className={cn(
                      "flex flex-col items-start gap-1 rounded-lg border p-2.5 text-left text-xs transition-colors cursor-pointer",
                      isSelected
                        ? "border-primary bg-primary/5 text-foreground font-medium"
                        : "border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                  >
                    <span className="font-semibold text-foreground">{lang.native}</span>
                    <span className="text-[10px] text-muted-foreground">{t(lang.label)}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Name display */}
          <div className="flex flex-col gap-2.5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium">{t("Name display format")}</p>
                <p className="text-xs text-muted-foreground">
                  {t("Choose how your name appears in the top navigation bar, report cards, and headers.")}
                </p>
              </div>
              {savingKey === "name_display" && <Loader2 className="size-4 animate-spin text-muted-foreground" />}
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 pt-1">
              {NAME_DISPLAY_OPTIONS.map((format) => {
                const isSelected = (accountPrefs.name_display ?? "full_name") === format.value
                return (
                  <button
                    key={format.value}
                    type="button"
                    onClick={() => updateNamespace("account", { name_display: format.value }, "name_display")}
                    className={cn(
                      "flex items-center justify-between rounded-lg border p-3 text-left text-xs transition-colors cursor-pointer",
                      isSelected
                        ? "border-primary bg-primary/5 text-foreground font-medium"
                        : "border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                  >
                    <div>
                      <p className="font-medium text-foreground">{t(format.label)}</p>
                      <p className="text-[11px] text-muted-foreground font-mono mt-0.5">{format.example}</p>
                    </div>
                    {isSelected && <Check className="size-4 text-primary shrink-0" />}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </SectionCard>

      {/* 3. Notification Preferences: Grade Alerts, Attendance Warnings, Semester Results */}
      <SectionCard
        icon={Bell}
        title="Notification preferences"
        description="Control what notifications and alerts you receive."
      >
        <div className="flex flex-col divide-y divide-border/60">
          <div className="flex items-center justify-between gap-4 py-3 first:pt-0">
            <div className="min-w-0">
              <p className="text-sm font-medium">{t("Grade alerts")}</p>
              <p className="text-xs text-muted-foreground">
                {t("Get notified when new midterm, internal, or evaluation grades are published.")}
              </p>
            </div>
            <Switch
              checked={Boolean(notifPrefs.grade_alerts ?? true)}
              onCheckedChange={(checked) =>
                updateNamespace("notifications", { grade_alerts: checked }, "Grade alerts")
              }
              aria-label={t("Grade alerts")}
            />
          </div>

          <div className="flex items-center justify-between gap-4 py-3">
            <div className="min-w-0">
              <p className="text-sm font-medium">{t("Attendance warnings")}</p>
              <p className="text-xs text-muted-foreground">
                {t("Alerts when subject attendance approaches or falls below the 75% eligibility threshold.")}
              </p>
            </div>
            <Switch
              checked={Boolean(notifPrefs.attendance_warnings ?? true)}
              onCheckedChange={(checked) =>
                updateNamespace("notifications", { attendance_warnings: checked }, "Attendance warnings")
              }
              aria-label={t("Attendance warnings")}
            />
          </div>

          <div className="flex items-center justify-between gap-4 py-3 last:pb-0">
            <div className="min-w-0">
              <p className="text-sm font-medium">{t("Semester results")}</p>
              <p className="text-xs text-muted-foreground">
                {t("Be notified when end-semester summary cards and SGPA/CGPA calculations are finalized.")}
              </p>
            </div>
            <Switch
              checked={Boolean(notifPrefs.semester_results ?? true)}
              onCheckedChange={(checked) =>
                updateNamespace("notifications", { semester_results: checked }, "Semester results")
              }
              aria-label={t("Semester results")}
            />
          </div>
        </div>
      </SectionCard>

      {/* 4. Security: Change Password, 2FA, Sign Out All Devices */}
      <SectionCard
        icon={Lock}
        title="Security & Sign-in"
        description="Protect your account, change your password, and manage active sessions."
      >
        <div className="flex flex-col gap-6">
          {/* Change Password Form */}
          <div className="border-b border-border/60 pb-6">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div>
                <p className="text-sm font-medium flex items-center gap-1.5">
                  <KeyRound className="size-4 text-muted-foreground" />
                  {t("Change password")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("Update your credentials securely. Password must be at least 6 characters.")}
                </p>
              </div>
              {secPrefs.password_updated_at ? (
                <span className="text-[11px] text-muted-foreground">
                  Last changed: {String(secPrefs.password_updated_at).split("T")[0]}
                </span>
              ) : null}
            </div>

            {passwordError && (
              <div className="mb-3 flex items-center gap-2 rounded-lg bg-destructive/10 p-2.5 text-xs text-destructive">
                <AlertCircle className="size-4 shrink-0" />
                <span>{passwordError}</span>
              </div>
            )}
            {passwordSuccess && (
              <div className="mb-3 flex items-center gap-2 rounded-lg bg-emerald-500/10 p-2.5 text-xs text-emerald-600">
                <CheckCircle2 className="size-4 shrink-0" />
                <span>{passwordSuccess}</span>
              </div>
            )}

            <form onSubmit={handlePasswordChange} className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:max-w-xl">
              <div>
                <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                  {t("Current password")}
                </label>
                <Input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="••••••••"
                  className="h-8 text-xs"
                  required
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                  {t("New password")}
                </label>
                <Input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  className="h-8 text-xs"
                  required
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                  {t("Confirm new password")}
                </label>
                <Input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="h-8 text-xs"
                  required
                />
              </div>
              <div className="sm:col-span-3 flex justify-start pt-1">
                <Button type="submit" size="sm" disabled={isChangingPassword} className="h-8 text-xs cursor-pointer">
                  {isChangingPassword ? (
                    <>
                      <Loader2 className="size-3.5 animate-spin mr-1.5" />
                      {t("Updating...")}
                    </>
                  ) : (
                    t("Update password")
                  )}
                </Button>
              </div>
            </form>
          </div>

          {/* Two-Factor Authentication */}
          <div className="flex items-center justify-between gap-4 border-b border-border/60 pb-6">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium flex items-center gap-1.5">
                  <Smartphone className="size-4 text-muted-foreground" />
                  {t("Two-factor authentication")}
                </p>
                <Badge variant={secPrefs.two_factor_enabled ? "success" : "muted"}>
                  {secPrefs.two_factor_enabled ? t("Enabled") : t("Disabled")}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {t("Require email verification code sent to your student institutional address when signing in.")}
              </p>
            </div>
            <Switch
              checked={Boolean(secPrefs.two_factor_enabled)}
              onCheckedChange={handleToggleTwoFactor}
              aria-label={t("Two-factor authentication")}
            />
          </div>

          {/* Sign Out All Devices */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-medium flex items-center gap-1.5">
                <LogOut className="size-4 text-muted-foreground" />
                {t("Sign out all devices")}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("Terminates all active sessions across other browsers, tablets, and phones.")}
              </p>
            </div>
            {showSignOutConfirm ? (
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={handleSignOutAll}
                  disabled={isSigningOutAll}
                  className="h-8 text-xs cursor-pointer"
                >
                  {isSigningOutAll ? <Loader2 className="size-3.5 animate-spin mr-1" /> : <ShieldAlert className="size-3.5 mr-1" />}
                  {t("Confirm sign out all")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowSignOutConfirm(false)}
                  className="h-8 text-xs cursor-pointer"
                >
                  {t("Cancel")}
                </Button>
              </div>
            ) : (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowSignOutConfirm(true)}
                className="h-8 text-xs cursor-pointer text-destructive border-destructive/30 hover:bg-destructive/10"
              >
                {t("Sign out all devices")}
              </Button>
            )}
          </div>
        </div>
      </SectionCard>

      {/* 5. Session Information */}
      <SectionCard
        icon={ShieldCheck}
        title="Session information"
        description="Details about your current signed-in session."
      >
        {session ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-medium">{t("Signed in as")} {session.username}</p>
                <p className="text-xs text-muted-foreground">
                  {session.department ?? t("No department")} · {t("Student")}
                </p>
              </div>
              <Badge variant="success">{t("Active session")}</Badge>
            </div>
            <div className="grid gap-x-6 gap-y-1 border-t border-border/60 pt-3 text-sm sm:grid-cols-2">
              <p className="text-muted-foreground">
                {t("Role:")} <span className="font-medium text-foreground">{t("Student")}</span>
              </p>
              {session.studentId && (
                <p className="text-muted-foreground">
                  {t("Student ID:")} <span className="font-medium text-foreground">{session.studentId}</span>
                </p>
              )}
              {session.department && (
                <p className="text-muted-foreground">
                  {t("Department:")}{" "}
                  <span className="font-medium text-foreground">{session.department}</span>
                </p>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("Session details are unavailable right now.")}
          </p>
        )}
      </SectionCard>

      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <ShieldCheck className="size-4" />
        {t("You can sign out from the sidebar or the account menu in the header.")}
      </div>
    </div>
  )
}
