import type { ChatModelAdapter } from "@assistant-ui/react"

// ─── Configuration ──────────────────────────────────────────────────────────
// Set VITE_USE_MOCK_CHAT=true in .env to use the mock adapter.
// Default: mock enabled (so the UI works without a running backend).

const USE_MOCK = import.meta.env.VITE_USE_MOCK_CHAT !== "false"
const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

// Mock adapter

const MOCK_RESPONSES = [
  `Great choice! Based on what you've told me, I'm going to recommend a build focused on **high-performance gaming at 1440p**.

Let me start putting together your parts list. I'll walk you through each component and why I picked it.

**CPU: AMD Ryzen 7 7800X3D**
The 7800X3D is the best gaming CPU on the market right now. Its 3D V-Cache technology gives it a significant edge in frame rates across virtually all titles — often 10-20% ahead of competitors at the same price point.`,

  `**Motherboard: MSI MAG B650 TOMAHAWK WIFI**
A solid mid-range B650 board with excellent VRM thermals, built-in WiFi 6E, and plenty of M.2 slots. It pairs perfectly with the 7800X3D without overspending on X670 features you won't need.

**RAM: G.Skill Trident Z5 Neo 32GB (2x16GB) DDR5-6000 CL30**
DDR5-6000 is the sweet spot for Ryzen 7000 series — it aligns with the memory controller's preferred ratio for maximum performance.`,

  `I'd be happy to help you build a new PC! To get started, could you tell me a bit about what you'll primarily use it for? For example:

- **Gaming** — and if so, at what resolution and frame rate?
- **Creative work** — video editing, 3D rendering, music production?
- **AI/ML** — model training, fine-tuning, inference?
- **General productivity** — browsing, office apps, multitasking?
- **Streaming** — while gaming, or standalone?

Feel free to mention multiple use cases — I'll prioritize accordingly.`,
]

function randomDelay(min: number, max: number): Promise<void> {
  return new Promise((r) => setTimeout(r, min + Math.random() * (max - min)))
}

const mockAdapter: ChatModelAdapter = {
  async *run({ messages, abortSignal }) {
    const userMessage = messages[messages.length - 1]?.content
      .filter((p): p is { type: "text"; text: string } => p.type === "text")
      .map((p) => p.text)
      .join(" ")
      .toLowerCase() ?? ""

    // Pick a contextually appropriate mock response
    let response: string
    if (messages.length <= 1 || userMessage.includes("help") || userMessage.includes("start")) {
      response = MOCK_RESPONSES[2] // Welcome / elicitation
    } else if (userMessage.includes("gaming") || userMessage.includes("fps")) {
      response = MOCK_RESPONSES[0] // Gaming recommendation
    } else {
      response = MOCK_RESPONSES[1] // Continuation
    }

    // Simulate streaming: yield word-by-word with small delays
    const words = response.split(" ")
    let streamed = ""

    for (let i = 0; i < words.length; i++) {
      if (abortSignal?.aborted) return
      streamed += (i > 0 ? " " : "") + words[i]
      await randomDelay(15, 45)
      yield { content: [{ type: "text" as const, text: streamed }] }
    }
  },
}

// Real adapter

const realAdapter: ChatModelAdapter = {
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

// Export

export const modelAdapter: ChatModelAdapter = USE_MOCK ? mockAdapter : realAdapter