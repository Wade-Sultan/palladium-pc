import { createFileRoute } from "@tanstack/react-router"
 
import { UnderConstruction } from "@/components/Common/UnderConstruction"
 
export const Route = createFileRoute("/_layout/buildhistory")({
  component: BuildHistory,
  head: () => ({
    meta: [{ title: "My Builds" }],
  }),
})
 
function BuildHistory() {
  return <UnderConstruction pageName="My Builds" />
}
