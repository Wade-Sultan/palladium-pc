import { Thread } from "@/components/assistant-ui/thread"

export function ChatInterface() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-hidden">
        <Thread />
      </div>
    </div>
  )
}
