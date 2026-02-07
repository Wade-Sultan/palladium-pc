import { createFileRoute } from "@tanstack/react-router"

import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Dashboard - FastAPI Cloud",
      },
    ],
  }),
})

function Dashboard() {
  const { user: currentUser } = useAuth()
  const displayName = currentUser?.full_name || currentUser?.email || "there"
  const subtitle = currentUser
    ? "Welcome back, nice to see you again!!!"
    : "Welcome. Log in when you're ready to manage your account."

  return (
    <div>
      <div>
        <h1 className="text-2xl truncate max-w-sm">
          Hi, {displayName} 👋
        </h1>
        <p className="text-muted-foreground">{subtitle}</p>
      </div>
    </div>
  )
}
