import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth from "@/hooks/useAuth"
import { supabase } from "@/lib/supabase"
import { cn } from "@/lib/utils"

const formSchema = z.object({
  full_name: z.string().max(30).optional(),
  email: z.string().email({ message: "Invalid email address" }),
})

type FormData = z.infer<typeof formSchema>

const UserInformation = () => {
  const { user } = useAuth()
  const [editMode, setEditMode] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const currentFullName = (user?.user_metadata?.full_name as string) ?? ""
  const currentEmail = user?.email ?? ""

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      full_name: currentFullName,
      email: currentEmail,
    },
  })

  const toggleEditMode = () => {
    setEditMode(!editMode)
  }

  const onSubmit = async (data: FormData) => {
    if (submitting) return
    setSubmitting(true)
    setError(null)

    // Update user metadata (full_name) and email via Supabase
    const updates: { email?: string; data?: { full_name?: string } } = {}

    if (data.full_name !== currentFullName) {
      updates.data = { full_name: data.full_name }
    }
    if (data.email !== currentEmail) {
      updates.email = data.email
    }

    if (Object.keys(updates).length === 0) {
      setEditMode(false)
      setSubmitting(false)
      return
    }

    const { error: updateError } = await supabase.auth.updateUser(updates)

    if (updateError) {
      setError(updateError.message)
    } else {
      setEditMode(false)
    }

    setSubmitting(false)
  }

  const onCancel = () => {
    form.reset()
    setError(null)
    toggleEditMode()
  }

  return (
    <div className="max-w-md">
      <h3 className="text-lg font-semibold py-4">User Information</h3>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-4"
        >
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <FormField
            control={form.control}
            name="full_name"
            render={({ field }) =>
              editMode ? (
                <FormItem>
                  <FormLabel>Full name</FormLabel>
                  <FormControl>
                    <Input type="text" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              ) : (
                <FormItem>
                  <FormLabel>Full name</FormLabel>
                  <p
                    className={cn(
                      "py-2 truncate max-w-sm",
                      !field.value && "text-muted-foreground",
                    )}
                  >
                    {field.value || "N/A"}
                  </p>
                </FormItem>
              )
            }
          />

          <FormField
            control={form.control}
            name="email"
            render={({ field }) =>
              editMode ? (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input type="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              ) : (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <p className="py-2 truncate max-w-sm">{field.value}</p>
                </FormItem>
              )
            }
          />

          <div className="flex gap-3">
            {editMode ? (
              <>
                <LoadingButton
                  type="submit"
                  loading={submitting}
                  disabled={!form.formState.isDirty}
                >
                  Save
                </LoadingButton>
                <Button
                  type="button"
                  variant="outline"
                  onClick={onCancel}
                  disabled={submitting}
                >
                  Cancel
                </Button>
              </>
            ) : (
              <Button type="button" onClick={toggleEditMode}>
                Edit
              </Button>
            )}
          </div>
        </form>
      </Form>
    </div>
  )
}

export default UserInformation
