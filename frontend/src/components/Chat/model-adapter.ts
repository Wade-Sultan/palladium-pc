import type { ChatModelAdapter } from "@assistant-ui/react"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export const modelAdapter: ChatModelAdapter = {
  async *run({ messages, abortSignal }) {
    const response = await fetch(`${API_BASE}/api/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: messages.map((m) => ({
          role: m.role,
          content: m.content
            .filter((p): p is { type: "text"; text: string } => p.type === "text")
            .map((p) => p.text)
            .join("\n"),
        })),
      }),
      signal: abortSignal,
    })

    if (!response.ok) {
      throw new Error(`Chat API returned ${response.status}: ${response.statusText}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error("No response body")

    const decoder = new TextDecoder()
    let fullText = ""

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        // Parse SSE lines: "data: {...}\n\n"
        const lines = chunk.split("\n")

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          const data = line.slice(6).trim()

          if (data === "[DONE]") break

          try {
            const parsed = JSON.parse(data)

            // Handle different event types from the pipeline
            if (parsed.type === "token" || parsed.type === "content") {
              fullText += parsed.text ?? parsed.content ?? ""
              yield { content: [{ type: "text" as const, text: fullText }] }
            } else if (parsed.type === "progress") {
              // Pipeline step progress — inline as blockquote
              fullText += `\n\n> **${parsed.step}**: ${parsed.message}\n\n`
              yield { content: [{ type: "text" as const, text: fullText }] }
            }
          } catch {
            // Non-JSON line, skip
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },
}
