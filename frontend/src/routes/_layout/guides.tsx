import { createFileRoute } from "@tanstack/react-router"

import { UnderConstruction } from "@/components/Common/UnderConstruction"

export const Route = createFileRoute("/_layout/guides")({
  component: Guides,
  head: () => ({
    meta: [{ title: "Guides" }],
  }),
})

function Guides() {
  return <UnderConstruction pageName="Guides" />
}
