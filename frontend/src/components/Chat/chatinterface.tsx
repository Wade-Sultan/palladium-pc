import { useState } from "react"
import {
  Thread,
  ThreadWelcome,
  Composer,
  type ThreadConfig,
} from "@assistant-ui/react"
import { makeMarkdownText } from "@assistant-ui/react-markdown"
import { Cpu, ArrowLeft } from "lucide-react"
import { useNavigate } from "@tanstack/react-router"

import { Button } from "@/components/ui/button"
import { ChatRuntimeProvider, SUGGESTED_PROMPTS } from "./ChatRuntimeProvider"

// ─── Markdown renderer for assistant messages ───────────────────────────────

const MarkdownText = makeMarkdownText()

// ─── Thread configuration ───────────────────────────────────────────────────

const threadConfig: ThreadConfig = {
  assistantMessage: {
    components: {
      Text: MarkdownText,
    },
  },
  strings: {
    composer: {
      placeholder: "Describe your ideal PC build...",
    },
    threadWelcome: {
      title: undefined, // We provide a custom welcome
      message: undefined,
    },
  },
}

// ─── Welcome screen component ───────────────────────────────────────────────

function WelcomeScreen() {
  return (
    <ThreadWelcome.Root>
      <div className="flex flex-col items-center gap-6 px-4 pt-8 pb-4">
        {/* Logo mark */}
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 ring-1 ring-primary/20">
          <Cpu className="h-7 w-7 text-primary" />
        </div>

        {/* Heading */}
        <div className="text-center">
          <h1 className="text-2xl font-semibold tracking-tight">
            Let's build your PC
          </h1>
          <p className="mt-2 max-w-md text-sm text-muted-foreground leading-relaxed">
            Tell me what you need and I'll put together a complete, compatible
            parts list — optimized for your use case and budget.
          </p>
        </div>

        {/* Suggested prompts */}
        <div className="grid w-full max-w-lg grid-cols-1 gap-2 sm:grid-cols-2">
          {SUGGESTED_PROMPTS.map(({ prompt, icon }) => (
            <ThreadWelcome.Suggestion
              key={prompt}
              prompt={prompt}
              method="replace"
            >
              <button
                type="button"
                className="group flex w-full items-start gap-3 rounded-xl border border-border/50 bg-card/50 p-3.5 text-left text-sm transition-all hover:border-primary/30 hover:bg-accent/50 active:scale-[0.98]"
              >
                <span className="mt-0.5 text-base leading-none">{icon}</span>
                <span className="text-muted-foreground leading-snug group-hover:text-foreground transition-colors">
                  {prompt}
                </span>
              </button>
            </ThreadWelcome.Suggestion>
          ))}
        </div>
      </div>
    </ThreadWelcome.Root>
  )
}

// ─── Main ChatInterface ─────────────────────────────────────────────────────

export function ChatInterface() {
  const navigate = useNavigate()

  return (
    <ChatRuntimeProvider>
      <div className="flex h-[calc(100vh-4rem)] flex-col">
        {/* Chat header */}
        <div className="flex items-center gap-3 border-b px-4 py-3">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={() => navigate({ to: "/" })}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
              <Cpu className="h-4 w-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-medium leading-none">
                Palladium Builder
              </h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                AI-powered PC recommendations
              </p>
            </div>
          </div>
        </div>

        {/* Thread area */}
        <Thread.Root
          config={threadConfig}
          className="flex-1 flex flex-col"
        >
          <Thread.Viewport className="flex-1 overflow-y-auto">
            <WelcomeScreen />
            <Thread.Messages />
            <Thread.FollowupSuggestions />
          </Thread.Viewport>

          <div className="border-t bg-background/80 backdrop-blur-sm p-4">
            <div className="mx-auto max-w-2xl">
              <Composer.Root className="flex items-end gap-2 rounded-xl border bg-card p-2 shadow-sm focus-within:ring-1 focus-within:ring-ring">
                <Composer.Input
                  autoFocus
                  className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none"
                  rows={1}
                />
                <Composer.Send asChild>
                  <Button size="sm" className="h-8 px-3 shrink-0">
                    Send
                  </Button>
                </Composer.Send>
              </Composer.Root>
              <p className="mt-2 text-center text-[11px] text-muted-foreground/60">
                Palladium may make mistakes. Always verify compatibility before purchasing.
              </p>
            </div>
          </div>
        </Thread.Root>
      </div>
    </ChatRuntimeProvider>
  )
}