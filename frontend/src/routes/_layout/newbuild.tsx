import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_layout/newbuild')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/_layout/newbuild"!</div>
}
