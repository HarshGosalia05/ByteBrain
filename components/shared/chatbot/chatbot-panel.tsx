import * as React from "react"
import { cn } from "@/lib/utils"

export function ChatbotPanel({
  isOpen,
  isMinimized,
  onClose,
  children,
  className,
}: {
  isOpen: boolean
  isMinimized: boolean
  onClose: () => void
  children: React.ReactNode
  className?: string
}) {
  // Handle escape key to close
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <>
      {/* Mobile backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-xs sm:hidden animate-in fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Responsive Panel Container - Floating Bottom-Right on Desktop */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="AI Chat Assistant"
        className={cn(
          "fixed z-50 flex flex-col bg-card text-card-foreground border border-border shadow-2xl transition-all duration-200 overflow-hidden",
          // Mobile styles (viewport overlay with top margin)
          "inset-x-3 bottom-3 top-16 rounded-2xl",
          // Desktop styles: strictly anchored to bottom-right corner
          "sm:top-auto sm:left-auto sm:bottom-20 sm:right-5 sm:w-[420px] sm:max-w-[calc(100vw-2.5rem)] sm:rounded-2xl",
          isMinimized
            ? "sm:h-14"
            : "sm:h-[580px] sm:max-h-[calc(100vh-7rem)]",
          className
        )}
      >
        {children}
      </div>
    </>
  )
}
