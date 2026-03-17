import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_layout/buildhistory')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/_layout/buildhistory"!</div>
}
