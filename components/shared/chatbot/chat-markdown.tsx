import * as React from "react"

/**
 * Pure React safe Markdown renderer without dangerouslySetInnerHTML.
 * Parses headings, lists, bold, italics, inline code, code blocks, and blockquotes.
 */
export function ChatMarkdown({ content }: { content: string }) {
  const lines = content.split("\n")
  const elements: React.ReactNode[] = []
  let inCodeBlock = false
  let codeBlockBuffer: string[] = []
  let codeBlockLang = ""

  lines.forEach((line, idx) => {
    // Code block start/end
    if (line.startsWith("```")) {
      if (!inCodeBlock) {
        inCodeBlock = true
        codeBlockLang = line.slice(3).trim()
        codeBlockBuffer = []
      } else {
        inCodeBlock = false
        elements.push(
          <div
            key={`codeblock-${idx}`}
            className="my-2 rounded-md bg-zinc-950 p-2.5 font-mono text-xs text-zinc-100 dark:bg-zinc-900 border border-zinc-800 overflow-x-auto"
          >
            {codeBlockLang && (
              <div className="mb-1 text-[10px] uppercase tracking-wider text-zinc-400">
                {codeBlockLang}
              </div>
            )}
            <pre className="whitespace-pre-wrap">{codeBlockBuffer.join("\n")}</pre>
          </div>
        )
        codeBlockBuffer = []
      }
      return
    }

    if (inCodeBlock) {
      codeBlockBuffer.push(line)
      return
    }

    const trimmed = line.trim()

    // Empty line
    if (!trimmed) {
      elements.push(<div key={`blank-${idx}`} className="h-1.5" />)
      return
    }

    // Headings
    if (trimmed.startsWith("### ")) {
      elements.push(
        <h4 key={`h3-${idx}`} className="font-semibold text-xs mt-2 mb-1 text-foreground">
          {renderInline(trimmed.slice(4))}
        </h4>
      )
      return
    }
    if (trimmed.startsWith("## ")) {
      elements.push(
        <h3 key={`h2-${idx}`} className="font-bold text-sm mt-2 mb-1 text-foreground">
          {renderInline(trimmed.slice(3))}
        </h3>
      )
      return
    }
    if (trimmed.startsWith("# ")) {
      elements.push(
        <h2 key={`h1-${idx}`} className="font-bold text-base mt-2.5 mb-1.5 text-foreground">
          {renderInline(trimmed.slice(2))}
        </h2>
      )
      return
    }

    // Blockquote
    if (trimmed.startsWith("> ")) {
      elements.push(
        <blockquote
          key={`quote-${idx}`}
          className="border-l-2 border-primary/60 pl-2.5 py-0.5 my-1 text-xs italic text-muted-foreground bg-muted/30 rounded-r"
        >
          {renderInline(trimmed.slice(2))}
        </blockquote>
      )
      return
    }

    // Unordered List (- or *)
    if (/^[-*]\s+/.test(trimmed)) {
      elements.push(
        <div key={`li-${idx}`} className="flex items-start gap-1.5 pl-1 my-0.5">
          <span className="text-primary text-xs leading-5 select-none">•</span>
          <span className="text-xs leading-5 flex-1">{renderInline(trimmed.replace(/^[-*]\s+/, ""))}</span>
        </div>
      )
      return
    }

    // Ordered List (1. 2. etc)
    const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/)
    if (numMatch) {
      elements.push(
        <div key={`oli-${idx}`} className="flex items-start gap-1.5 pl-1 my-0.5">
          <span className="font-medium text-muted-foreground text-xs leading-5 select-none">
            {numMatch[1]}.
          </span>
          <span className="text-xs leading-5 flex-1">{renderInline(numMatch[2])}</span>
        </div>
      )
      return
    }

    // Regular paragraph
    elements.push(
      <p key={`p-${idx}`} className="text-xs leading-5 my-0.5 text-foreground">
        {renderInline(trimmed)}
      </p>
    )
  })

  // Flush any unclosed code block
  if (inCodeBlock && codeBlockBuffer.length > 0) {
    elements.push(
      <div
        key="codeblock-unclosed"
        className="my-2 rounded-md bg-zinc-950 p-2.5 font-mono text-xs text-zinc-100 border border-zinc-800 overflow-x-auto"
      >
        <pre className="whitespace-pre-wrap">{codeBlockBuffer.join("\n")}</pre>
      </div>
    )
  }

  return <div className="space-y-0.5 break-words">{elements}</div>
}

/**
 * Parses inline formatting: **bold**, *italic*, and `code`
 */
function renderInline(text: string): React.ReactNode[] {
  // Regex to token split on inline code (`...`), bold (**...**), italic (*...*)
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g)

  return tokens.map((token, i) => {
    if (!token) return null

    if (token.startsWith("`") && token.endsWith("`") && token.length >= 2) {
      return (
        <code
          key={i}
          className="rounded bg-muted px-1 py-0.5 font-mono text-[11px] text-foreground border border-border/60"
        >
          {token.slice(1, -1)}
        </code>
      )
    }

    if (token.startsWith("**") && token.endsWith("**") && token.length >= 4) {
      return (
        <strong key={i} className="font-semibold text-foreground">
          {token.slice(2, -2)}
        </strong>
      )
    }

    if (token.startsWith("*") && token.endsWith("*") && token.length >= 2) {
      return (
        <em key={i} className="italic">
          {token.slice(1, -1)}
        </em>
      )
    }

    return token
  })
}
