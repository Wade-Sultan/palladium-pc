import { useEffect, useState, useCallback } from "react"
import { useNavigate } from "@tanstack/react-router"
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  sendPasswordResetEmail,
  updatePassword as firebaseUpdatePassword,
  updateProfile,
  type User,
} from "firebase/auth"
import { auth } from "@/lib/firebase"
 
interface UseAuthReturn {
  user: User | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<{ error: Error | null }>
  signUp: (email: string, password: string, fullName?: string) => Promise<{ error: Error | null }>
  signOut: () => Promise<void>
  resetPassword: (email: string) => Promise<{ error: Error | null }>
  updatePassword: (newPassword: string) => Promise<{ error: Error | null }>
}
 
/**
 * Check if there's an active session without subscribing to changes.
 * Useful for route guards (beforeLoad) where hooks can't be used.
 */
export async function isLoggedIn(): Promise<boolean> {
  return new Promise((resolve) => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      unsubscribe()
      resolve(user !== null)
    })
  })
}
 
/**
 * Get the current ID token for passing to your FastAPI backend.
 * Returns null if no active session.
 */
export async function getAccessToken(): Promise<string | null> {
  const user = auth.currentUser
  if (!user) return null
  return user.getIdToken()
}
 
export default function useAuth(): UseAuthReturn {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
 
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUser(user)
      setLoading(false)
    })
    return () => unsubscribe()
  }, [])
 
  const signIn = useCallback(async (email: string, password: string) => {
    try {
      await signInWithEmailAndPassword(auth, email, password)
      navigate({ to: "/" })
      return { error: null }
    } catch (err) {
      return { error: err as Error }
    }
  }, [navigate])
 
  const signUp = useCallback(async (email: string, password: string, fullName?: string) => {
    try {
      const { user } = await createUserWithEmailAndPassword(auth, email, password)
      if (fullName) {
        await updateProfile(user, { displayName: fullName })
      }
      // Navigate to login. Firebase may require email verification
      // depending on your project settings.
      navigate({ to: "/login" })
      return { error: null }
    } catch (err) {
      return { error: err as Error }
    }
  }, [navigate])
 
  const signOut = useCallback(async () => {
    await firebaseSignOut(auth)
    navigate({ to: "/login" })
  }, [navigate])
 
  const resetPassword = useCallback(async (email: string) => {
    try {
      await sendPasswordResetEmail(auth, email, {
        url: `${window.location.origin}/reset-password`,
      })
      return { error: null }
    } catch (err) {
      return { error: err as Error }
    }
  }, [])
 
  const updatePassword = useCallback(async (newPassword: string) => {
    try {
      if (!auth.currentUser) throw new Error("No authenticated user")
      await firebaseUpdatePassword(auth.currentUser, newPassword)
      navigate({ to: "/" })
      return { error: null }
    } catch (err) {
      return { error: err as Error }
    }
  }, [navigate])
 
  return { user, loading, signIn, signUp, signOut, resetPassword, updatePassword }
}
