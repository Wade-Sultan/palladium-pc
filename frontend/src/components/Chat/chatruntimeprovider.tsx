import type { ReactNode } from "react"
import {
  AssistantRuntimeProvider,
  useLocalRuntime,
} from "@assistant-ui/react"

import { modelAdapter } from "./model-adapter"

const SUGGESTED_PROMPTS = [
  {
    prompt: "I want to build a gaming PC for 1440p 144fps",
    icon: "🎮",
  },
  {
    prompt: "Help me build a workstation for AI model training",
    icon: "🧠",
  },
  {
    prompt: "I need a quiet, compact PC for video editing",
    icon: "🎬",
  },
  {
    prompt: "Build me a budget-friendly PC for general use and light gaming",
    icon: "💡",
  },
]

interface ChatRuntimeProviderProps {
  children: ReactNode
}

export { SUGGESTED_PROMPTS }

export function ChatRuntimeProvider({ children }: ChatRuntimeProviderProps) {
  const runtime = useLocalRuntime(modelAdapter, {
    initialMessages: [],
  })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  )
}