import { createFileRoute } from "@tanstack/react-router"

import { UnderConstruction } from "@/components/Common/UnderConstruction"

export const Route = createFileRoute("/_layout/findbuilder")({
  component: FindBuilder,
  head: () => ({
    meta: [{ title: "Find a Builder" }],
  }),
})

function FindBuilder() {
  return <UnderConstruction pageName="Find a Builder" />
}
