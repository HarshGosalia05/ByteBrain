import * as React from "react"
import { cn } from "@/lib/utils"

export function ChatbotPanel({
  isOpen,
  isMinimized,
  isExpanded,
  onClose,
  children,
  className,
}: {
  isOpen: boolean
  isMinimized: boolean
  isExpanded: boolean
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
          "fixed z-50 flex flex-col bg-card text-card-foreground border border-border shadow-2xl overflow-hidden",
          "transition-[width,height,top,left,right,margin] duration-300 ease-in-out",
          // Minimized always uses compact layout
          isMinimized
            ? "inset-x-3 bottom-3 top-16 rounded-2xl sm:top-auto sm:left-auto sm:bottom-20 sm:right-5 sm:w-[420px] sm:max-w-[calc(100vw-2.5rem)] sm:rounded-2xl sm:h-14"
            : isExpanded
            ? "inset-x-2 bottom-2 top-2 rounded-xl sm:top-[8vh] sm:left-[10vw] sm:bottom-auto sm:right-auto sm:w-[80vw] sm:h-[84vh] sm:max-w-[1200px] sm:max-h-[84vh] sm:rounded-2xl"
            : "inset-x-3 bottom-3 top-16 rounded-2xl sm:top-auto sm:left-auto sm:bottom-20 sm:right-5 sm:w-[420px] sm:max-w-[calc(100vw-2.5rem)] sm:rounded-2xl sm:h-[580px] sm:max-h-[calc(100vh-7rem)]",
          className
        )}
      >
        {children}
      </div>
    </>
  )
}
