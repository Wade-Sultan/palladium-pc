import { useState } from "react"
import { useForm } from "react-hook-form"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth from "@/hooks/useAuth"
import { supabase } from "@/lib/supabase"

const DeleteConfirmation = () => {
  const { handleSubmit } = useForm()
  const { signOut } = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async () => {
    setLoading(true)
    setError(null)

    // Note: Supabase doesn't expose user self-deletion from the client SDK.
    // This calls a backend endpoint you'll create on FastAPI that uses the
    // Supabase Admin API (service_role key) to delete the user.
    // For now, this signs the user out. Replace the fetch call below once
    // your backend endpoint is ready.
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        await signOut()
        return
      }

      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/api/v1/users/me`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
        },
      )

      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.detail || "Failed to delete account")
      }

      await signOut()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="destructive" className="mt-3">
          Delete Account
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Confirmation Required</DialogTitle>
            <DialogDescription>
              All your account data will be{" "}
              <strong>permanently deleted.</strong> If you are sure, please
              click <strong>"Confirm"</strong> to proceed. This action cannot be
              undone.
            </DialogDescription>
          </DialogHeader>

          {error && (
            <p className="text-sm text-destructive mt-2">{error}</p>
          )}

          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={loading}>
                Cancel
              </Button>
            </DialogClose>
            <LoadingButton
              variant="destructive"
              type="submit"
              loading={loading}
            >
              Delete
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default DeleteConfirmation
