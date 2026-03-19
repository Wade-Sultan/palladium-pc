import { createFileRoute } from "@tanstack/react-router"

import { ChatInterface } from "@/components/Chat/chatinterface"

export const Route = createFileRoute("/_layout/newbuild")({
  component: NewBuild,
  head: () => ({
    meta: [{ title: "New Build - Palladium" }],
  }),
})

function NewBuild() {
  return <ChatInterface />
}
