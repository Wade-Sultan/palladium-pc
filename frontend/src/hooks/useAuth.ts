import { useEffect, useState, useCallback } from "react"
import { useNavigate } from "@tanstack/react-router"
import type { User, Session, AuthError } from "@supabase/supabase-js"
import { supabase } from "@/lib/supabase"

interface UseAuthReturn {
  user: User | null
  session: Session | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<{ error: AuthError | null }>
  signUp: (email: string, password: string, fullName?: string) => Promise<{ error: AuthError | null }>
  signOut: () => Promise<void>
  resetPassword: (email: string) => Promise<{ error: AuthError | null }>
  updatePassword: (newPassword: string) => Promise<{ error: AuthError | null }>
}

/**
 * Check if there's an active session without subscribing to changes.
 * Useful for route guards (beforeLoad) where hooks can't be used.
 */
export async function isLoggedIn(): Promise<boolean> {
  const { data } = await supabase.auth.getSession()
  return data.session !== null
}

/**
 * Get the current access token for passing to your FastAPI backend.
 * Returns null if no active session.
 */
export async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}

export default function useAuth(): UseAuthReturn {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Initial session load
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        setUser(session?.user ?? null)
        setLoading(false)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (!error) {
      navigate({ to: "/" })
    }
    return { error }
  }, [navigate])

  const signUp = useCallback(async (email: string, password: string, fullName?: string) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
        },
      },
    })
    if (!error) {
      // Supabase may require email confirmation depending on your project settings.
      // Navigate to login so they can confirm and sign in.
      navigate({ to: "/login" })
    }
    return { error }
  }, [navigate])

  const signOut = useCallback(async () => {
    await supabase.auth.signOut()
    navigate({ to: "/login" })
  }, [navigate])

  const resetPassword = useCallback(async (email: string) => {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    })
    return { error }
  }, [])

  const updatePassword = useCallback(async (newPassword: string) => {
    const { error } = await supabase.auth.updateUser({ password: newPassword })
    if (!error) {
      navigate({ to: "/" })
    }
    return { error }
  }, [navigate])

  return {
    user,
    session,
    loading,
    signIn,
    signUp,
    signOut,
    resetPassword,
    updatePassword,
  }
}
