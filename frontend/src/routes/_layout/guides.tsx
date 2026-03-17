import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_layout/guides')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/_layout/guides"!</div>
}
