"use client"

import useAuth from "@/hooks/useAuth"

export default function DashboardPage() {
  const { user } = useAuth()
  const displayName = user?.displayName || user?.email || "there"

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
