import { Thread } from "@/components/assistant-ui/thread"
import { ChatRuntimeProvider } from "./chatruntimeprovider"

export function ChatInterface() {
  return (
    <ChatRuntimeProvider>
      <div className="flex h-full flex-col">
        <div className="flex-1 overflow-hidden">
          <Thread />
        </div>
      </div>
    </ChatRuntimeProvider>
  )
}
