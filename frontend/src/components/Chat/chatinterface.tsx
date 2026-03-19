import { useNavigate } from "@tanstack/react-router"
import { Cpu, ArrowLeft } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Thread } from "@/components/assistant-ui/thread"
import { ChatRuntimeProvider } from "./chatruntimeprovider"

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
        <div className="flex-1 overflow-hidden">
          <Thread />
        </div>
      </div>
    </ChatRuntimeProvider>
  )
}