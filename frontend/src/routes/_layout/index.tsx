import { createFileRoute } from "@tanstack/react-router"

import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [{ title: "Dashboard - Palladium" }],
  }),
})

function Dashboard() {
  const { user } = useAuth()
  const displayName =
    (user?.user_metadata?.full_name as string) || user?.email || "there"

  return (
    <div>
      <div>
        <h1 className="text-2xl truncate max-w-sm">Hi, {displayName} 👋</h1>
        <p className="text-muted-foreground">
          Welcome back, nice to see you again!
        </p>
      </div>
    </div>
  )
}