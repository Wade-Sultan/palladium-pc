"use client"

import { useRouter } from "next/navigation"
import { useEffect } from "react"
import type { ReactNode } from "react"
import useAuth from "@/hooks/useAuth"

export default function ClientAuthGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/signup")
    }
  }, [user, loading, router])

  if (loading || !user) return null
  return <>{children}</>
}
